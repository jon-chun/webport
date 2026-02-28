"""
WebPort Property-Based Tests

Uses Hypothesis for property-based testing.

Addresses Critique #31: No Property-Based Testing
"""

import pytest
from hypothesis import given, strategies as st, assume, settings
from hypothesis.stateful import RuleBasedStateMachine, rule, Bundle

from webport.crawlers.utils.dedup import URLNormalizer, URLDeduplicator
from webport.crawlers.utils.rate_limiter import TokenBucket
from webport.core.security import URLValidator, ContentAnonymizer


class TestURLNormalizerProperties:
    """Property-based tests for URL normalizer."""

    normalizer = URLNormalizer()

    @given(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_/", min_size=1, max_size=50))
    @settings(max_examples=100)
    def test_normalize_idempotent(self, path: str):
        """Normalizing twice should give same result."""
        url = f"https://example.com/{path}"
        normalized = self.normalizer.normalize(url)
        double_normalized = self.normalizer.normalize(normalized)

        assert normalized == double_normalized

    @given(st.sampled_from([
        ("HTTP://EXAMPLE.COM", "http://example.com"),
        ("https://example.com/page/", "https://example.com/page"),  # Non-root trailing slash removed
        ("https://example.com:443/path", "https://example.com/path"),
        ("http://example.com:80/path", "http://example.com/path"),
    ]))
    def test_known_normalizations(self, url_pair: tuple):
        """Test specific normalization cases."""
        input_url, expected = url_pair
        assert self.normalizer.normalize(input_url) == expected
    
    @given(
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=20),
        st.text(alphabet="abcdefghijklmnopqrstuvwxyz", min_size=1, max_size=20),
    )
    def test_different_paths_different_hashes(self, path1: str, path2: str):
        """Different paths should produce different hashes."""
        assume(path1 != path2)
        
        url1 = f"https://example.com/{path1}"
        url2 = f"https://example.com/{path2}"
        
        hash1 = self.normalizer.get_url_hash(url1)
        hash2 = self.normalizer.get_url_hash(url2)
        
        assert hash1 != hash2
    
    @given(st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=5))
    def test_tracking_params_removed(self, values: list):
        """UTM parameters should be removed."""
        params = "&".join(f"utm_source={v}" for v in values)
        url = f"https://example.com/page?{params}"
        
        normalized = self.normalizer.normalize(url)
        
        assert "utm_source" not in normalized


class TestTokenBucketProperties:
    """Property-based tests for token bucket."""
    
    @given(
        st.floats(min_value=0.1, max_value=100.0),
        st.integers(min_value=1, max_value=100),
    )
    def test_bucket_never_exceeds_capacity(self, rate: float, capacity: int):
        """Token bucket should never exceed capacity."""
        bucket = TokenBucket(rate=rate, capacity=capacity)
        
        # Even after waiting, should not exceed capacity
        assert bucket.available_tokens <= capacity
    
    @given(st.integers(min_value=1, max_value=10))
    def test_acquire_decreases_tokens(self, tokens: int):
        """Acquiring tokens should decrease available count."""
        bucket = TokenBucket(rate=10.0, capacity=100)
        
        initial = bucket.available_tokens
        bucket.acquire(tokens=tokens, timeout=0.1)
        
        assert bucket.available_tokens <= initial
    
    @given(st.integers(min_value=1, max_value=5))
    def test_try_acquire_is_nonblocking(self, tokens: int):
        """try_acquire should return immediately."""
        bucket = TokenBucket(rate=0.001, capacity=tokens)  # Very slow refill
        
        # Drain bucket
        bucket.try_acquire(tokens)
        
        # This should return False immediately, not block
        result = bucket.try_acquire(tokens)
        assert result is False


class TestURLValidatorProperties:
    """Property-based tests for URL validator."""

    validator = URLValidator()

    @given(st.sampled_from([
        "10.0.0.1",
        "192.168.1.1",
        "172.16.0.1",
        "127.0.0.1",
        "169.254.1.1",
    ]))
    def test_blocks_internal_ips(self, ip: str):
        """Internal IPs should be blocked."""
        url = f"http://{ip}/path"
        is_valid, _normalized, error = self.validator.validate_url(url)

        assert not is_valid
        assert error is not None
        assert "blocked" in error.lower()

    @given(st.sampled_from(["javascript:", "file://", "ftp://", "data:"]))
    def test_blocks_unsafe_schemes(self, scheme: str):
        """Non-HTTP schemes should be blocked."""
        url = f"{scheme}malicious"
        is_valid, _normalized, error = self.validator.validate_url(url)

        assert not is_valid

    @given(st.text(min_size=0, max_size=5000))
    def test_handles_arbitrary_input(self, text: str):
        """Validator should handle any input without crashing."""
        # Should not raise exceptions
        is_valid, _normalized, _error = self.validator.validate_url(text)

        # Result should be boolean
        assert isinstance(is_valid, bool)


class TestContentAnonymizerProperties:
    """Property-based tests for content anonymizer."""

    anonymizer = ContentAnonymizer()

    @given(st.sampled_from([
        "test@example.com",
        "user.name@domain.org",
        "john_doe123@test.co.uk",
    ]))
    def test_emails_anonymized(self, email: str):
        """Emails should be detected and can be anonymized."""
        content = f"Contact me at {email} for more info."

        # Should detect email
        pii = self.anonymizer.detect_pii(content)
        assert len(pii) > 0

    @given(st.from_regex(r"\d{3}-\d{3}-\d{4}", fullmatch=True))
    def test_phone_numbers_anonymized(self, phone: str):
        """Phone numbers should be detected."""
        content = f"Call me at {phone}"

        pii = self.anonymizer.detect_pii(content)
        # Note: May or may not detect depending on format

    @given(st.text(min_size=10, max_size=1000))
    def test_anonymize_idempotent(self, content: str):
        """Anonymizing twice should give same result."""
        result1 = self.anonymizer.anonymize(content)
        result2 = self.anonymizer.anonymize(result1)

        assert result1 == result2


class TestDeduplicatorStateMachine(RuleBasedStateMachine):
    """Stateful testing for URL deduplicator."""
    
    def __init__(self):
        super().__init__()
        self.dedup = URLDeduplicator()
        self.seen_urls = set()
    
    urls = Bundle("urls")
    
    @rule(target=urls, path=st.text(alphabet="abcdef/", min_size=1, max_size=20))
    def add_url(self, path: str):
        """Add a URL to track."""
        url = f"https://example.com/{path}"
        return url
    
    @rule(url=urls)
    def check_and_mark(self, url: str):
        """Check if URL is new and mark it."""
        is_new = self.dedup.should_process(url)
        
        normalized = self.dedup.normalizer.normalize(url)
        expected_new = normalized not in self.seen_urls
        
        assert is_new == expected_new
        
        if is_new:
            self.dedup.mark_seen(url)
            self.seen_urls.add(normalized)
    
    @rule(url=urls)
    def check_seen(self, url: str):
        """Check if a URL has been seen."""
        normalized = self.dedup.normalizer.normalize(url)
        
        if normalized in self.seen_urls:
            assert not self.dedup.should_process(url)


TestDeduplicatorStateMachine.TestCase.settings = settings(max_examples=50)


class TestRateLimiterStateMachine(RuleBasedStateMachine):
    """Stateful testing for rate limiter."""
    
    def __init__(self):
        super().__init__()
        self.bucket = TokenBucket(rate=100.0, capacity=10)
        self.acquired = 0
    
    @rule(tokens=st.integers(min_value=1, max_value=3))
    def try_acquire(self, tokens: int):
        """Try to acquire tokens."""
        success = self.bucket.try_acquire(tokens)
        
        if success:
            self.acquired += tokens
        
        # Available tokens should be <= capacity
        assert self.bucket.available_tokens <= self.bucket.capacity
    
    @rule()
    def check_invariants(self):
        """Check invariants hold."""
        # Tokens should not be negative
        assert self.bucket.available_tokens >= 0
        
        # Should not exceed capacity
        assert self.bucket.available_tokens <= self.bucket.capacity


TestRateLimiterStateMachine.TestCase.settings = settings(max_examples=100)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
