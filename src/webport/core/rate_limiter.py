"""
WebPort Rate Limiter

Token bucket rate limiting with per-domain tracking.

Addresses Critique #8: Rate Limiting Implementation Incomplete
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
        self.last_refill = time.monotonic()
        self._lock = threading.Lock()
    
    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now
    
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


@dataclass
class DomainRateLimit:
    """Per-domain rate limit state."""
    bucket: TokenBucket
    concurrent_semaphore: asyncio.Semaphore
    sync_semaphore: threading.Semaphore
    retry_after: Optional[datetime] = None
    total_requests: int = 0
    throttled_requests: int = 0
    total_wait_time: float = 0.0


class DomainRateLimiter:
    """Rate limiter with per-domain tracking."""
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self._domains: Dict[str, DomainRateLimit] = {}
        self._lock = threading.Lock()
    
    def _get_domain(self, url: str) -> str:
        if "://" in url:
            return urlparse(url).netloc
        return url
    
    def _get_rate_limit(self, domain: str) -> DomainRateLimit:
        if domain not in self._domains:
            rate = self.config.domain_overrides.get(domain, self.config.requests_per_second)
            self._domains[domain] = DomainRateLimit(
                bucket=TokenBucket(rate, self.config.burst_size),
                concurrent_semaphore=asyncio.Semaphore(self.config.concurrent_requests),
                sync_semaphore=threading.Semaphore(self.config.concurrent_requests),
            )
        return self._domains[domain]
    
    def acquire(self, url: str, timeout: Optional[float] = None) -> bool:
        domain = self._get_domain(url)
        with self._lock:
            limit = self._get_rate_limit(domain)
        
        # Check retry-after
        if limit.retry_after and datetime.utcnow() < limit.retry_after:
            wait = (limit.retry_after - datetime.utcnow()).total_seconds()
            if timeout and wait > timeout:
                return False
            time.sleep(wait)
        
        start = time.monotonic()
        limit.sync_semaphore.acquire()
        try:
            result = limit.bucket.acquire(timeout=timeout)
            if result:
                limit.total_requests += 1
            else:
                limit.throttled_requests += 1
            limit.total_wait_time += time.monotonic() - start
            return result
        except Exception:
            limit.sync_semaphore.release()
            raise
    
    async def async_acquire(self, url: str, timeout: Optional[float] = None) -> bool:
        domain = self._get_domain(url)
        with self._lock:
            limit = self._get_rate_limit(domain)
        
        if limit.retry_after and datetime.utcnow() < limit.retry_after:
            wait = (limit.retry_after - datetime.utcnow()).total_seconds()
            if timeout and wait > timeout:
                return False
            await asyncio.sleep(wait)
        
        start = time.monotonic()
        await limit.concurrent_semaphore.acquire()
        try:
            result = await limit.bucket.async_acquire(timeout=timeout)
            if result:
                limit.total_requests += 1
            else:
                limit.throttled_requests += 1
            limit.total_wait_time += time.monotonic() - start
            return result
        except Exception:
            limit.concurrent_semaphore.release()
            raise
    
    def release(self, url: str) -> None:
        domain = self._get_domain(url)
        if domain in self._domains:
            self._domains[domain].sync_semaphore.release()
    
    async def async_release(self, url: str) -> None:
        domain = self._get_domain(url)
        if domain in self._domains:
            self._domains[domain].concurrent_semaphore.release()
    
    def record_rate_limit(self, url: str, retry_after: int = 60) -> None:
        domain = self._get_domain(url)
        with self._lock:
            limit = self._get_rate_limit(domain)
        limit.retry_after = datetime.utcnow() + timedelta(seconds=retry_after)
        logger.warning(f"Rate limited on {domain}, waiting {retry_after}s")
    
    def get_stats(self) -> Dict[str, Dict]:
        stats = {}
        for domain, limit in self._domains.items():
            stats[domain] = {
                "total_requests": limit.total_requests,
                "throttled_requests": limit.throttled_requests,
                "throttle_rate": (
                    limit.throttled_requests / limit.total_requests * 100
                    if limit.total_requests > 0 else 0
                ),
                "avg_wait_time": (
                    limit.total_wait_time / limit.total_requests
                    if limit.total_requests > 0 else 0
                ),
            }
        return stats


class RateLimitContext:
    """Context manager for rate limiting."""
    
    def __init__(self, limiter: DomainRateLimiter, url: str):
        self.limiter = limiter
        self.url = url
    
    def __enter__(self):
        self.limiter.acquire(self.url)
        return self
    
    def __exit__(self, *args):
        self.limiter.release(self.url)
    
    async def __aenter__(self):
        await self.limiter.async_acquire(self.url)
        return self
    
    async def __aexit__(self, *args):
        await self.limiter.async_release(self.url)


_rate_limiter: Optional[DomainRateLimiter] = None


def get_rate_limiter(config: Optional[RateLimitConfig] = None) -> DomainRateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = DomainRateLimiter(config)
    return _rate_limiter


def rate_limited(url: str) -> RateLimitContext:
    return RateLimitContext(get_rate_limiter(), url)


__all__ = [
    "RateLimitConfig",
    "TokenBucket",
    "DomainRateLimiter",
    "RateLimitContext",
    "get_rate_limiter",
    "rate_limited",
]
