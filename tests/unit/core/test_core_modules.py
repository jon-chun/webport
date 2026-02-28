"""
Unit tests for WebPort core modules.
"""

import pytest
from datetime import datetime
from pathlib import Path


class TestExceptions:
    """Tests for exception hierarchy."""
    
    def test_webport_error_base(self):
        from webport.core.exceptions import WebPortError
        
        error = WebPortError("Test error")
        assert str(error) == "Test error"
        assert error.message == "Test error"
    
    def test_http_error_with_status(self):
        from webport.core.exceptions import HTTPError

        error = HTTPError("https://example.com", 404)
        assert error.context.url == "https://example.com"  # URL is in context
        assert error.status_code == 404
        assert "404" in str(error)

    def test_rate_limit_error(self):
        from webport.core.exceptions import RateLimitError

        error = RateLimitError("https://example.com", retry_after=60)
        assert error.retry_after == 60

    def test_error_summary(self):
        from webport.core.exceptions import ErrorSummary, NetworkError

        summary = ErrorSummary()
        summary.add(NetworkError("Connection failed"))  # add() not record()
        summary.add(NetworkError("Connection failed"))

        assert summary.total_errors == 2
        assert "NetworkError" in summary.by_type


class TestConfig:
    """Tests for configuration system."""
    
    def test_default_config(self):
        from webport.core.config import WebPortConfig
        
        config = WebPortConfig(target_url="https://example.com")
        assert config.target_url == "https://example.com"
        assert config.ethics.respect_robots_txt is True
    
    def test_environment_enum(self):
        from webport.core.config import Environment
        
        assert Environment.PRODUCTION.value == "production"
        assert Environment.DEVELOPMENT.value == "development"
    
    def test_ethics_config_defaults(self):
        from webport.core.config import EthicsConfig
        
        ethics = EthicsConfig()
        assert ethics.rate_limit == 2.0
        assert ethics.respect_robots_txt is True


class TestModels:
    """Tests for Pydantic models."""
    
    def test_page_metadata(self):
        from webport.core.models import PageMetadata
        
        meta = PageMetadata(title="Test", description="A test page")
        assert meta.title == "Test"
        assert meta.keywords == []
    
    def test_crawled_page(self):
        from webport.core.models import CrawledPage
        
        page = CrawledPage(url="https://example.com", status_code=200)
        assert page.url == "https://example.com"
        assert page.depth == 0
    
    def test_wordpress_post(self):
        from webport.core.models import WordPressPost
        
        post = WordPressPost(
            id=1,
            slug="test-post",
            title="Test Post",
            content="<p>Content</p>",
        )
        assert post.id == 1
        assert post.type == "post"


class TestSecurity:
    """Tests for security module."""

    def test_url_validator_blocks_internal_ips(self):
        from webport.core.security import URLValidator

        validator = URLValidator()

        # Should block internal IPs (validate_url returns 3 values)
        is_valid, _normalized, _error = validator.validate_url("http://127.0.0.1/admin")
        assert not is_valid

        is_valid, _normalized, _error = validator.validate_url("http://192.168.1.1/")
        assert not is_valid

    def test_url_validator_allows_valid_urls(self):
        from webport.core.security import URLValidator

        validator = URLValidator()

        is_valid, _normalized, _error = validator.validate_url("https://example.com/page")
        assert is_valid
    
    def test_content_anonymizer(self):
        from webport.core.security import ContentAnonymizer
        
        anonymizer = ContentAnonymizer()
        
        content = "Contact john@example.com for info"
        result = anonymizer.anonymize(content)
        
        assert "john@example.com" not in result
        assert "[EMAIL]" in result


class TestCheckpoint:
    """Tests for checkpoint system."""

    def test_checkpoint_creation(self, tmp_path):
        from webport.core.checkpoint import CheckpointManager

        manager = CheckpointManager(checkpoint_dir=tmp_path)
        checkpoint = manager.get_or_create(
            target_url="https://example.com",
            force_new=True,
        )

        assert checkpoint.target_url == "https://example.com"
        assert checkpoint.progress.total_completed == 0  # total_completed not total_crawled

    def test_checkpoint_add_url(self, tmp_path):
        from webport.core.checkpoint import CheckpointManager

        manager = CheckpointManager(checkpoint_dir=tmp_path)
        checkpoint = manager.get_or_create(
            target_url="https://example.com",
            force_new=True,
        )

        checkpoint.add_discovered_url("https://example.com/page1", depth=1)
        # url_queue contains target_url + page1
        assert len(checkpoint.url_queue) == 2


class TestRetry:
    """Tests for retry and circuit breaker."""

    def test_circuit_breaker_initial_state(self):
        from webport.core.retry import CircuitBreaker, CircuitBreakerConfig, CircuitState

        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker(domain="example.com", config=config)
        assert cb.state == CircuitState.CLOSED

    def test_circuit_breaker_opens_on_failures(self):
        from webport.core.retry import CircuitBreaker, CircuitBreakerConfig, CircuitState

        config = CircuitBreakerConfig(failure_threshold=3)
        cb = CircuitBreaker(domain="example.com", config=config)

        for _ in range(3):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN


class TestMetrics:
    """Tests for metrics collection."""

    def test_crawl_metrics(self):
        from webport.core.metrics import CrawlMetrics

        metrics = CrawlMetrics()
        assert metrics.pages_crawled == 0
        # success_rate returns 100.0 when no pages crawled (no failures = 100% success)
        assert metrics.success_rate == 100.0
    
    def test_metrics_collector(self):
        from webport.core.metrics import MetricsCollector
        
        collector = MetricsCollector()
        collector.start()
        
        collector.record_request(
            url="https://example.com",
            status_code=200,
            bytes_size=1000,
            latency_ms=100,
            success=True,
        )
        
        metrics = collector.get_metrics()
        assert metrics.pages_crawled == 1


class TestPlugins:
    """Tests for plugin system."""

    def test_plugin_registration(self):
        from webport.core.plugins import BasePlugin, PluginRegistry

        class TestPlugin(BasePlugin):
            name = "test_plugin"
            version = "1.0.0"

        registry = PluginRegistry()
        registry.register(TestPlugin)

        # Use get_plugin instead of is_registered
        assert registry.get_plugin("test_plugin") is not None
    
    def test_plugin_info(self):
        from webport.core.plugins import BasePlugin
        
        class TestPlugin(BasePlugin):
            name = "test"
            version = "1.0.0"
            description = "Test plugin"
        
        plugin = TestPlugin()
        info = plugin.get_info()
        
        assert info.name == "test"
        assert info.version == "1.0.0"


class TestContainer:
    """Tests for dependency injection container."""

    def test_singleton_registration(self):
        from webport.core.container import Container, Lifetime

        class Service:
            def __init__(self):
                pass

        container = Container()
        container.register_factory(Service, lambda: Service(), lifetime=Lifetime.SINGLETON)

        instance1 = container.get(Service)
        instance2 = container.get(Service)

        assert instance1 is instance2

    def test_transient_registration(self):
        from webport.core.container import Container, Lifetime

        class Service:
            def __init__(self):
                pass

        container = Container()
        container.register_factory(Service, lambda: Service(), lifetime=Lifetime.TRANSIENT)

        instance1 = container.get(Service)
        instance2 = container.get(Service)

        assert instance1 is not instance2

    def test_scoped_registration(self):
        from webport.core.container import Container, Lifetime

        class Service:
            def __init__(self):
                pass

        container = Container()
        container.register_factory(Service, lambda: Service(), lifetime=Lifetime.SCOPED)

        with container.scope() as scope:
            instance1 = scope.get(Service)
            instance2 = scope.get(Service)
            assert instance1 is instance2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
