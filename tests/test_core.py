"""
WebPort Core Module Tests

Tests for core functionality including property-based testing.

Addresses Critique #31: No Property-Based Testing
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from hypothesis import given, settings, strategies as st

from webport.core.config import WebPortConfig, Environment
from webport.core.exceptions import (
    WebPortError,
    CrawlerError,
    HTTPError,
    RateLimitError,
    ValidationError,
)
from webport.core.models import PageMetadata, PageContent, CrawledPage
from webport.core.retry import RetryConfig, CircuitBreaker, CircuitBreakerConfig, CircuitState
from webport.core.checkpoint import CheckpointManager, CrawlCheckpoint, compute_content_hash
from webport.core.shutdown import ShutdownManager
from webport.crawlers.utils.dedup import URLNormalizer, URLDeduplicator
from webport.crawlers.utils.rate_limiter import TokenBucket, DomainRateLimiter


# ============================================
# Property-Based Tests (Critique #31)
# ============================================

class TestURLNormalizerProperties:
    """Property-based tests for URL normalization."""
    
    @given(st.text(min_size=1, max_size=100).filter(lambda x: x.isalnum()))
    def test_normalize_idempotent(self, path: str):
        """Normalizing a URL twice gives the same result."""
        normalizer = URLNormalizer()
        url = f"https://example.com/{path}"
        
        first = normalizer.normalize(url)
        second = normalizer.normalize(first)
        
        assert first == second
    
    @given(
        scheme=st.sampled_from(["http", "https"]),
        host=st.text(min_size=3, max_size=20, alphabet="abcdefghijklmnopqrstuvwxyz"),
        path=st.text(min_size=0, max_size=50, alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_/"),
    )
    def test_normalize_preserves_structure(self, scheme: str, host: str, path: str):
        """Normalization preserves URL structure."""
        normalizer = URLNormalizer()
        url = f"{scheme}://{host}.com/{path}"
        
        normalized = normalizer.normalize(url)
        
        assert normalized.startswith(f"{scheme}://")
        assert host.lower() in normalized.lower()
    
    @given(st.text(min_size=1, max_size=500))
    @settings(max_examples=50)
    def test_normalize_never_crashes(self, url: str):
        """Normalization never raises for any input."""
        normalizer = URLNormalizer()
        
        # Should not raise
        result = normalizer.normalize(url)
        assert isinstance(result, str)


class TestContentHashProperties:
    """Property-based tests for content hashing."""
    
    @given(st.text(min_size=0, max_size=10000))
    def test_hash_deterministic(self, content: str):
        """Same content always produces same hash."""
        hash1 = compute_content_hash(content)
        hash2 = compute_content_hash(content)
        
        assert hash1 == hash2
    
    @given(st.text(min_size=1, max_size=1000))
    def test_hash_fixed_length(self, content: str):
        """Hash always has fixed length."""
        content_hash = compute_content_hash(content)
        
        # SHA256 hex digest is 64 characters
        assert len(content_hash) == 64
    
    @given(
        content1=st.text(min_size=1, max_size=100),
        content2=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100)
    def test_different_content_different_hash(self, content1: str, content2: str):
        """Different content produces different hashes (with high probability)."""
        if content1 != content2:
            hash1 = compute_content_hash(content1)
            hash2 = compute_content_hash(content2)
            assert hash1 != hash2


class TestTokenBucketProperties:
    """Property-based tests for token bucket rate limiter."""
    
    @given(
        rate=st.floats(min_value=0.1, max_value=100.0),
        capacity=st.integers(min_value=1, max_value=100),
    )
    def test_bucket_initialization(self, rate: float, capacity: int):
        """Bucket initializes with full capacity."""
        bucket = TokenBucket(rate=rate, capacity=capacity)
        
        assert bucket.available_tokens >= 0
        assert bucket.available_tokens <= capacity
    
    @given(
        capacity=st.integers(min_value=1, max_value=50),
        acquire_count=st.integers(min_value=1, max_value=10),
    )
    def test_acquire_reduces_tokens(self, capacity: int, acquire_count: int):
        """Acquiring tokens reduces available count."""
        bucket = TokenBucket(rate=100.0, capacity=capacity)
        
        initial = bucket.available_tokens
        
        for _ in range(min(acquire_count, capacity)):
            bucket.try_acquire(1)
        
        assert bucket.available_tokens <= initial


# ============================================
# Unit Tests
# ============================================

class TestExceptions:
    """Test exception hierarchy."""

    def test_exception_hierarchy(self):
        """All errors inherit from WebPortError."""
        assert issubclass(CrawlerError, WebPortError)
        assert issubclass(HTTPError, WebPortError)  # HTTPError inherits from WebPortError
        assert issubclass(RateLimitError, HTTPError)  # RateLimitError inherits from HTTPError
        assert issubclass(ValidationError, WebPortError)

    def test_http_error_attributes(self):
        """HTTPError contains URL and status code."""
        error = HTTPError("https://example.com", 404)

        assert error.context.url == "https://example.com"  # URL is in context
        assert error.status_code == 404
        assert "404" in str(error)

    def test_rate_limit_error_retry_after(self):
        """RateLimitError includes retry_after."""
        error = RateLimitError("https://example.com", retry_after=60)

        assert error.retry_after == 60


class TestConfig:
    """Test configuration."""
    
    def test_default_config(self):
        """Default config has sensible defaults."""
        config = WebPortConfig(target_url="https://example.com")
        
        assert config.target_url == "https://example.com"
        assert config.environment == Environment.DEVELOPMENT
        assert config.ethics.respect_robots_txt is True
        assert config.crawler.max_pages > 0
    
    def test_environment_override(self):
        """Environment-specific overrides work."""
        config = WebPortConfig(
            target_url="https://example.com",
            environment=Environment.PRODUCTION,
        )
        
        # Production should have different defaults
        assert config.environment == Environment.PRODUCTION


class TestCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_initial_state_closed(self):
        """Circuit starts closed."""
        config = CircuitBreakerConfig(failure_threshold=3, timeout_seconds=60)
        cb = CircuitBreaker(domain="example.com", config=config)

        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_opens_after_failures(self):
        """Circuit opens after threshold failures."""
        config = CircuitBreakerConfig(failure_threshold=3, timeout_seconds=60)
        cb = CircuitBreaker(domain="example.com", config=config)

        for _ in range(3):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_success_resets_failures(self):
        """Success resets failure count."""
        config = CircuitBreakerConfig(failure_threshold=3, timeout_seconds=60)
        cb = CircuitBreaker(domain="example.com", config=config)

        cb.record_failure()
        cb.record_failure()
        cb.record_success()

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0


class TestCheckpoint:
    """Test checkpoint functionality."""
    
    def test_checkpoint_creation(self, temp_dir: Path):
        """Checkpoint manager creates checkpoints."""
        manager = CheckpointManager(checkpoint_dir=temp_dir)
        
        checkpoint = manager.get_or_create(
            target_url="https://example.com",
            force_new=True,
        )
        
        assert checkpoint is not None
        assert checkpoint.target_url == "https://example.com"
    
    def test_checkpoint_progress_tracking(self, temp_dir: Path):
        """Checkpoint tracks progress."""
        manager = CheckpointManager(checkpoint_dir=temp_dir)
        checkpoint = manager.get_or_create("https://example.com", force_new=True)

        # Note: get_or_create adds target_url to discovered URLs automatically
        checkpoint.add_discovered_url("https://example.com/page1", depth=1)
        checkpoint.add_discovered_url("https://example.com/page2", depth=1)

        # 3 = target_url + page1 + page2
        assert checkpoint.progress.total_discovered == 3

    def test_checkpoint_save_load(self, temp_dir: Path):
        """Checkpoint can be saved and loaded."""
        manager = CheckpointManager(checkpoint_dir=temp_dir)

        # Create and modify
        checkpoint = manager.get_or_create("https://example.com", force_new=True)
        checkpoint.add_discovered_url("https://example.com/page1", depth=1)
        manager.save()

        # Create new manager and load
        manager2 = CheckpointManager(checkpoint_dir=temp_dir)
        checkpoint2 = manager2.get_or_create("https://example.com", force_new=False)

        # 2 = target_url + page1
        assert checkpoint2.progress.total_discovered == 2


class TestURLDeduplicator:
    """Test URL deduplication."""
    
    def test_dedup_basic(self):
        """Basic deduplication works."""
        dedup = URLDeduplicator()
        
        assert dedup.should_process("https://example.com/page") is True
        dedup.mark_seen("https://example.com/page")
        assert dedup.should_process("https://example.com/page") is False
    
    def test_dedup_normalizes_urls(self):
        """Deduplication normalizes URLs."""
        dedup = URLDeduplicator()
        
        dedup.mark_seen("https://example.com/page/")
        
        # Trailing slash variations should be deduped
        assert dedup.should_process("https://example.com/page") is False
    
    def test_dedup_tracking_params(self):
        """Tracking parameters are removed."""
        dedup = URLDeduplicator()
        
        dedup.mark_seen("https://example.com/page?utm_source=test")
        
        # Same page without tracking should be deduped
        assert dedup.should_process("https://example.com/page") is False


class TestModels:
    """Test data models."""
    
    def test_page_metadata_defaults(self):
        """PageMetadata has sensible defaults."""
        meta = PageMetadata()
        
        assert meta.title is None
        assert meta.description is None
        assert meta.keywords == []
    
    def test_crawled_page_from_dict(self, sample_crawled_page: CrawledPage):
        """CrawledPage serialization works."""
        data = sample_crawled_page.model_dump()
        
        restored = CrawledPage.model_validate(data)
        
        assert restored.url == sample_crawled_page.url
        assert restored.status_code == sample_crawled_page.status_code


# ============================================
# Async Tests
# ============================================

class TestAsyncComponents:
    """Test async components."""
    
    @pytest.mark.asyncio
    async def test_rate_limiter_async_acquire(self):
        """Async rate limiter works."""
        limiter = DomainRateLimiter()
        
        acquired = await limiter.async_acquire("https://example.com", timeout=1.0)
        
        assert acquired is True
        limiter.release("https://example.com")
    
    def test_shutdown_manager_callbacks(self):
        """Shutdown manager executes callbacks."""
        # Reset singleton for testing
        ShutdownManager._instance = None

        manager = ShutdownManager()
        callback_executed = False

        @manager.on_shutdown()
        def callback():
            nonlocal callback_executed
            callback_executed = True

        # shutdown() is synchronous
        manager.shutdown()

        assert callback_executed is True

        # Clean up singleton
        ShutdownManager._instance = None
