"""
WebPort Rate Limiter

Token bucket rate limiting with per-domain support.

Addresses Critique #8: Rate Limiter Not Implemented
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_second: float = 2.0
    burst_size: int = 10
    concurrent_requests: int = 5
    domain_overrides: Dict[str, float] = field(default_factory=dict)


class TokenBucket:
    """Token bucket rate limiter."""
    
    def __init__(self, rate: float, capacity: int):
        self.rate = rate
        self.capacity = capacity
        self.tokens = float(capacity)
        self.last_update = time.monotonic()
        self._lock = threading.Lock()
    
    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_update = now
    
    def acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        deadline = time.monotonic() + timeout if timeout else None
        
        while True:
            with self._lock:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
            
            if deadline and time.monotonic() >= deadline:
                return False
            
            wait_time = (tokens - self.tokens) / self.rate
            time.sleep(min(wait_time, 0.1))
    
    async def async_acquire(self, tokens: int = 1, timeout: Optional[float] = None) -> bool:
        deadline = time.monotonic() + timeout if timeout else None
        
        while True:
            with self._lock:
                self._refill()
                if self.tokens >= tokens:
                    self.tokens -= tokens
                    return True
            
            if deadline and time.monotonic() >= deadline:
                return False
            
            wait_time = (tokens - self.tokens) / self.rate
            await asyncio.sleep(min(wait_time, 0.1))
    
    def try_acquire(self, tokens: int = 1) -> bool:
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    @property
    def available_tokens(self) -> float:
        with self._lock:
            self._refill()
            return self.tokens


@dataclass
class DomainRateLimitState:
    """State for a domain's rate limiting."""
    bucket: TokenBucket
    concurrent: int = 0
    max_concurrent: int = 5
    retry_after: Optional[datetime] = None
    total_requests: int = 0
    throttled_requests: int = 0
    total_wait_time: float = 0.0


class DomainRateLimiter:
    """Per-domain rate limiter with concurrent request tracking."""
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self._domains: Dict[str, DomainRateLimitState] = {}
        self._lock = threading.Lock()
    
    def _get_domain_state(self, url: str) -> DomainRateLimitState:
        domain = urlparse(url).netloc if "://" in url else url
        
        with self._lock:
            if domain not in self._domains:
                rate = self.config.domain_overrides.get(domain, self.config.requests_per_second)
                self._domains[domain] = DomainRateLimitState(
                    bucket=TokenBucket(rate, self.config.burst_size),
                    max_concurrent=self.config.concurrent_requests,
                )
            return self._domains[domain]
    
    def acquire(self, url: str, timeout: Optional[float] = None) -> bool:
        state = self._get_domain_state(url)
        start = time.monotonic()
        
        # Check retry-after
        if state.retry_after and datetime.utcnow() < state.retry_after:
            wait = (state.retry_after - datetime.utcnow()).total_seconds()
            if timeout and wait > timeout:
                return False
            time.sleep(wait)
        
        # Check concurrent limit
        while state.concurrent >= state.max_concurrent:
            if timeout and (time.monotonic() - start) >= timeout:
                return False
            time.sleep(0.05)
        
        # Acquire token
        remaining_timeout = None
        if timeout:
            remaining_timeout = timeout - (time.monotonic() - start)
            if remaining_timeout <= 0:
                return False
        
        if not state.bucket.acquire(timeout=remaining_timeout):
            state.throttled_requests += 1
            return False
        
        with self._lock:
            state.concurrent += 1
            state.total_requests += 1
            state.total_wait_time += time.monotonic() - start
        
        return True
    
    async def async_acquire(self, url: str, timeout: Optional[float] = None) -> bool:
        state = self._get_domain_state(url)
        start = time.monotonic()
        
        # Check retry-after
        if state.retry_after and datetime.utcnow() < state.retry_after:
            wait = (state.retry_after - datetime.utcnow()).total_seconds()
            if timeout and wait > timeout:
                return False
            await asyncio.sleep(wait)
        
        # Check concurrent limit
        while state.concurrent >= state.max_concurrent:
            if timeout and (time.monotonic() - start) >= timeout:
                return False
            await asyncio.sleep(0.05)
        
        # Acquire token
        remaining_timeout = None
        if timeout:
            remaining_timeout = timeout - (time.monotonic() - start)
            if remaining_timeout <= 0:
                return False
        
        if not await state.bucket.async_acquire(timeout=remaining_timeout):
            state.throttled_requests += 1
            return False
        
        with self._lock:
            state.concurrent += 1
            state.total_requests += 1
            state.total_wait_time += time.monotonic() - start
        
        return True
    
    def release(self, url: str) -> None:
        state = self._get_domain_state(url)
        with self._lock:
            state.concurrent = max(0, state.concurrent - 1)
    
    def record_rate_limit(self, url: str, retry_after: Optional[int] = None) -> None:
        state = self._get_domain_state(url)
        with self._lock:
            state.throttled_requests += 1
            if retry_after:
                state.retry_after = datetime.utcnow() + timedelta(seconds=retry_after)
    
    def get_stats(self) -> Dict[str, Dict]:
        with self._lock:
            return {
                domain: {
                    "total_requests": state.total_requests,
                    "throttled_requests": state.throttled_requests,
                    "throttle_rate": (
                        state.throttled_requests / state.total_requests * 100
                        if state.total_requests > 0 else 0
                    ),
                    "avg_wait_time": (
                        state.total_wait_time / state.total_requests
                        if state.total_requests > 0 else 0
                    ),
                    "current_concurrent": state.concurrent,
                }
                for domain, state in self._domains.items()
            }


class RateLimitContext:
    """Context manager for rate-limited requests."""
    
    def __init__(self, limiter: DomainRateLimiter, url: str, timeout: Optional[float] = None):
        self.limiter = limiter
        self.url = url
        self.timeout = timeout
        self.acquired = False
    
    def __enter__(self) -> "RateLimitContext":
        self.acquired = self.limiter.acquire(self.url, self.timeout)
        if not self.acquired:
            raise TimeoutError(f"Rate limit timeout for {self.url}")
        return self
    
    def __exit__(self, *args) -> None:
        if self.acquired:
            self.limiter.release(self.url)
    
    async def __aenter__(self) -> "RateLimitContext":
        self.acquired = await self.limiter.async_acquire(self.url, self.timeout)
        if not self.acquired:
            raise TimeoutError(f"Rate limit timeout for {self.url}")
        return self
    
    async def __aexit__(self, *args) -> None:
        if self.acquired:
            self.limiter.release(self.url)


# Global rate limiter
_rate_limiter: Optional[DomainRateLimiter] = None


def get_rate_limiter(config: Optional[RateLimitConfig] = None) -> DomainRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = DomainRateLimiter(config)
    return _rate_limiter


def rate_limited(url: str, timeout: Optional[float] = None) -> RateLimitContext:
    return RateLimitContext(get_rate_limiter(), url, timeout)


__all__ = [
    "RateLimitConfig",
    "TokenBucket",
    "DomainRateLimiter",
    "RateLimitContext",
    "get_rate_limiter",
    "rate_limited",
]
