"""
WebPort Retry & Circuit Breaker System

Production-ready retry mechanism with:
- Exponential backoff with jitter
- Circuit breaker pattern
- Per-domain tracking
- Statistics

Addresses Critique #1: No Retry/Backoff Implementation
Addresses Critique #5: No Circuit Breaker Pattern
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, TypeVar
from urllib.parse import urlparse

from tenacity import (
    AsyncRetrying,
    RetryCallState,
    Retrying,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from webport.core.exceptions import (
    CircuitBreakerOpenError,
    HTTPError,
    NetworkError,
    RateLimitError,
    ServerError,
    TimeoutError,
    WebPortError,
)

logger = logging.getLogger(__name__)
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class RetryConfig:
    """Retry configuration."""
    max_attempts: int = 3
    max_delay_seconds: float = 300.0
    initial_wait_seconds: float = 1.0
    max_wait_seconds: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retry_on_status_codes: Set[int] = field(default_factory=lambda: {
        408, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524
    })


@dataclass
class RetryStats:
    """Retry statistics."""
    total_attempts: int = 0
    successful_attempts: int = 0
    failed_attempts: int = 0
    total_retries: int = 0
    total_wait_time: float = 0.0
    domain_stats: Dict[str, Dict[str, int]] = field(default_factory=dict)
    
    def record_attempt(self, url: str, success: bool, attempt: int, wait_time: float = 0.0) -> None:
        domain = urlparse(url).netloc if url else "unknown"
        self.total_attempts += 1
        if success:
            self.successful_attempts += 1
        else:
            self.failed_attempts += 1
        if attempt > 1:
            self.total_retries += 1
            self.total_wait_time += wait_time
        
        if domain not in self.domain_stats:
            self.domain_stats[domain] = {"attempts": 0, "retries": 0, "failures": 0}
        self.domain_stats[domain]["attempts"] += 1
        if attempt > 1:
            self.domain_stats[domain]["retries"] += 1
        if not success:
            self.domain_stats[domain]["failures"] += 1


class CircuitState(Enum):
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: float = 60.0
    half_open_max_calls: int = 3


@dataclass
class CircuitBreaker:
    """Per-domain circuit breaker."""
    domain: str
    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    open_until: Optional[datetime] = None
    half_open_calls: int = 0
    half_open_successes: int = 0
    
    def can_execute(self) -> bool:
        self._maybe_transition()
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            return False
        if self.state == CircuitState.HALF_OPEN:
            return self.half_open_calls < self.config.half_open_max_calls
        return True
    
    def record_success(self) -> None:
        self.success_count += 1
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_successes += 1
            self.half_open_calls += 1
            if self.half_open_successes >= self.config.success_threshold:
                self._close()
    
    def record_failure(self, error: Optional[Exception] = None) -> None:
        self.failure_count += 1
        self.success_count = 0
        self.last_failure_time = datetime.utcnow()
        
        if self.state == CircuitState.HALF_OPEN:
            self._open()
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self._open()
    
    def _open(self) -> None:
        self.state = CircuitState.OPEN
        self.open_until = datetime.utcnow() + timedelta(seconds=self.config.timeout_seconds)
        logger.warning(f"[CircuitBreaker] {self.domain} -> OPEN until {self.open_until}")
    
    def _close(self) -> None:
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.half_open_calls = 0
        self.half_open_successes = 0
        self.open_until = None
        logger.info(f"[CircuitBreaker] {self.domain} -> CLOSED")
    
    def _maybe_transition(self) -> None:
        if self.state == CircuitState.OPEN and self.open_until:
            if datetime.utcnow() >= self.open_until:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                self.half_open_successes = 0
                logger.info(f"[CircuitBreaker] {self.domain} -> HALF_OPEN")


class CircuitBreakerManager:
    """Manages circuit breakers for multiple domains."""
    
    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self._breakers: Dict[str, CircuitBreaker] = {}
    
    def get_breaker(self, url: str) -> CircuitBreaker:
        domain = urlparse(url).netloc if "://" in url else url
        if domain not in self._breakers:
            self._breakers[domain] = CircuitBreaker(domain=domain, config=self.config)
        return self._breakers[domain]
    
    def check_and_raise(self, url: str) -> None:
        breaker = self.get_breaker(url)
        if not breaker.can_execute():
            raise CircuitBreakerOpenError(
                domain=breaker.domain,
                open_until=breaker.open_until or datetime.utcnow()
            )


# Global instances
_retry_stats = RetryStats()
_circuit_manager = CircuitBreakerManager()


def get_retry_stats() -> RetryStats:
    return _retry_stats


def get_circuit_manager() -> CircuitBreakerManager:
    return _circuit_manager


def should_retry(exception: Exception) -> bool:
    """Determine if exception should trigger retry."""
    if isinstance(exception, WebPortError):
        return exception.is_retryable
    if isinstance(exception, (ConnectionError, TimeoutError, NetworkError)):
        return True
    if isinstance(exception, HTTPError):
        return exception.status_code in RetryConfig().retry_on_status_codes
    return False


def with_retry(
    max_attempts: int = 3,
    initial_wait: float = 1.0,
    max_wait: float = 60.0,
    jitter: bool = True,
    circuit_breaker: bool = True,
) -> Callable[[F], F]:
    """Decorator for sync functions with retry support."""
    
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            url = None
            for arg in args:
                if isinstance(arg, str) and ("http://" in arg or "https://" in arg):
                    url = arg
                    break
            if not url:
                url = kwargs.get("url", "")
            
            if circuit_breaker and url:
                breaker = _circuit_manager.get_breaker(url)
                if not breaker.can_execute():
                    raise CircuitBreakerOpenError(
                        domain=breaker.domain,
                        open_until=breaker.open_until or datetime.utcnow()
                    )
            
            retryer = Retrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential_jitter(initial=initial_wait, max=max_wait),
                retry=retry_if_exception(should_retry),
                reraise=True,
            )
            
            try:
                for attempt in retryer:
                    with attempt:
                        result = func(*args, **kwargs)
                        if circuit_breaker and url:
                            _circuit_manager.get_breaker(url).record_success()
                        return result
            except Exception as e:
                if circuit_breaker and url:
                    _circuit_manager.get_breaker(url).record_failure(e)
                raise
        
        return wrapper  # type: ignore
    return decorator


def with_async_retry(
    max_attempts: int = 3,
    initial_wait: float = 1.0,
    max_wait: float = 60.0,
    jitter: bool = True,
    circuit_breaker: bool = True,
) -> Callable[[F], F]:
    """Decorator for async functions with retry support."""
    
    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            url = None
            for arg in args:
                if isinstance(arg, str) and ("http://" in arg or "https://" in arg):
                    url = arg
                    break
            if not url:
                url = kwargs.get("url", "")
            
            if circuit_breaker and url:
                breaker = _circuit_manager.get_breaker(url)
                if not breaker.can_execute():
                    raise CircuitBreakerOpenError(
                        domain=breaker.domain,
                        open_until=breaker.open_until or datetime.utcnow()
                    )
            
            retryer = AsyncRetrying(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential_jitter(initial=initial_wait, max=max_wait),
                retry=retry_if_exception(should_retry),
                reraise=True,
            )
            
            try:
                async for attempt in retryer:
                    with attempt:
                        result = await func(*args, **kwargs)
                        if circuit_breaker and url:
                            _circuit_manager.get_breaker(url).record_success()
                        return result
            except Exception as e:
                if circuit_breaker and url:
                    _circuit_manager.get_breaker(url).record_failure(e)
                raise
        
        return wrapper  # type: ignore
    return decorator


def calculate_backoff(attempt: int, initial: float = 1.0, maximum: float = 60.0, 
                      base: float = 2.0, jitter: bool = True) -> float:
    """Calculate backoff time for given attempt."""
    wait = min(initial * (base ** (attempt - 1)), maximum)
    if jitter:
        wait += random.uniform(-wait * 0.25, wait * 0.25)
    return max(0, wait)


__all__ = [
    "RetryConfig", "RetryStats", "CircuitState", "CircuitBreakerConfig",
    "CircuitBreaker", "CircuitBreakerManager", "get_retry_stats",
    "get_circuit_manager", "should_retry", "with_retry", "with_async_retry",
    "calculate_backoff",
]
