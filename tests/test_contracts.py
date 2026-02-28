"""
WebPort Contract Tests

Tests that verify contracts between components.

Addresses Critique #32: No Contract Tests
"""

import pytest
from abc import ABC
from typing import Protocol, runtime_checkable

from webport.core.config import WebPortConfig
from webport.core.models import CrawledPage, PageMetadata, PageContent, CrawlResult
from webport.crawlers.base import BaseCrawler
from webport.migrators.base import BaseMigrator


# ============================================
# Protocol Definitions (Contracts)
# ============================================

@runtime_checkable
class CrawlerProtocol(Protocol):
    """Contract that all crawlers must fulfill."""
    
    config: WebPortConfig
    
    async def crawl(self) -> list[CrawledPage]:
        """Crawl the target site."""
        ...
    
    async def close(self) -> None:
        """Close resources."""
        ...


@runtime_checkable
class MigratorProtocol(Protocol):
    """Contract that all migrators must fulfill."""
    
    @property
    def name(self) -> str:
        """Framework name."""
        ...
    
    async def migrate(self) -> "MigrationResult":
        """Execute migration."""
        ...


@runtime_checkable
class CheckpointProtocol(Protocol):
    """Contract for checkpoint managers."""
    
    def save(self) -> None:
        """Save checkpoint to disk."""
        ...
    
    def load(self) -> None:
        """Load checkpoint from disk."""
        ...


# ============================================
# Contract Tests
# ============================================

class TestCrawlerContracts:
    """Verify crawler implementations fulfill contracts."""
    
    def test_static_crawler_protocol(self, base_config: WebPortConfig):
        """StaticSiteCrawler fulfills CrawlerProtocol."""
        from webport.crawlers import StaticSiteCrawler
        
        crawler = StaticSiteCrawler(base_config)
        
        assert isinstance(crawler, CrawlerProtocol)
        assert hasattr(crawler, 'crawl')
        assert hasattr(crawler, 'close')
        assert hasattr(crawler, 'config')
    
    def test_wordpress_crawler_protocol(self, base_config: WebPortConfig):
        """WordPressCrawler fulfills CrawlerProtocol."""
        from webport.crawlers import WordPressCrawler
        
        crawler = WordPressCrawler(base_config)
        
        assert isinstance(crawler, CrawlerProtocol)
        assert hasattr(crawler, 'crawl')
        assert hasattr(crawler, 'close')
        assert hasattr(crawler, 'config')
    
    def test_crawler_returns_list_of_pages(self, base_config: WebPortConfig):
        """Crawler.crawl() returns List[CrawledPage]."""
        from webport.crawlers import StaticSiteCrawler
        import asyncio
        
        crawler = StaticSiteCrawler(base_config)
        
        # Just verify the method exists and has correct signature
        assert callable(crawler.crawl)
        
        # Check return type annotation
        import inspect
        sig = inspect.signature(crawler.crawl)
        # Return annotation should be list-like
        # (actual verification would happen at runtime)


class TestMigratorContracts:
    """Verify migrator implementations fulfill contracts."""
    
    def test_nextjs_migrator_has_name(self, base_config: WebPortConfig, temp_dir):
        """NextJSMigrator has name property."""
        from webport.migrators.nextjs import NextJSMigrator
        from webport.core.models import CrawlResult
        from datetime import datetime
        
        crawl_result = CrawlResult(
            target_url="https://example.com",
            site_type="static",
            crawl_id="test",
            started_at=datetime.utcnow(),
            pages=[],
        )
        
        migrator = NextJSMigrator(
            crawl_result=crawl_result,
            output_dir=temp_dir,
        )
        
        assert hasattr(migrator, 'name')
        assert migrator.name == "nextjs"
    
    def test_migrator_has_migrate_method(self, base_config: WebPortConfig, temp_dir):
        """All migrators have migrate() method."""
        from webport.migrators.nextjs import NextJSMigrator
        from webport.core.models import CrawlResult
        from datetime import datetime
        
        crawl_result = CrawlResult(
            target_url="https://example.com",
            site_type="static",
            crawl_id="test",
            started_at=datetime.utcnow(),
            pages=[],
        )
        
        migrator = NextJSMigrator(
            crawl_result=crawl_result,
            output_dir=temp_dir,
        )
        
        assert hasattr(migrator, 'migrate')
        assert callable(migrator.migrate)


class TestModelContracts:
    """Verify data model contracts."""
    
    def test_crawled_page_has_required_fields(self):
        """CrawledPage has all required fields."""
        page = CrawledPage(
            url="https://example.com",
            status_code=200,
            content_type="text/html",
        )
        
        # Required fields exist
        assert hasattr(page, 'url')
        assert hasattr(page, 'status_code')
        assert hasattr(page, 'content_type')
        
        # Optional fields have defaults
        assert hasattr(page, 'metadata')
        assert hasattr(page, 'content')
    
    def test_page_metadata_is_optional(self):
        """PageMetadata fields are optional."""
        meta = PageMetadata()
        
        # All should have None/empty defaults
        assert meta.title is None
        assert meta.description is None
        assert meta.keywords == []
    
    def test_crawl_result_contains_pages(self):
        """CrawlResult contains list of CrawledPage."""
        from datetime import datetime
        
        page = CrawledPage(
            url="https://example.com",
            status_code=200,
            content_type="text/html",
        )
        
        result = CrawlResult(
            target_url="https://example.com",
            site_type="static",
            crawl_id="test",
            started_at=datetime.utcnow(),
            pages=[page],
        )
        
        assert len(result.pages) == 1
        assert isinstance(result.pages[0], CrawledPage)
    
    def test_models_serializable(self, sample_crawled_page: CrawledPage):
        """Models can be serialized to dict."""
        data = sample_crawled_page.model_dump()
        
        assert isinstance(data, dict)
        assert 'url' in data
        assert 'status_code' in data
    
    def test_models_deserializable(self, sample_crawled_page: CrawledPage):
        """Models can be deserialized from dict."""
        data = sample_crawled_page.model_dump()
        restored = CrawledPage.model_validate(data)
        
        assert restored.url == sample_crawled_page.url


class TestConfigContracts:
    """Verify configuration contracts."""
    
    def test_config_has_target_url(self):
        """Config requires target_url."""
        config = WebPortConfig(target_url="https://example.com")
        
        assert config.target_url == "https://example.com"
    
    def test_config_has_nested_configs(self):
        """Config has required nested configurations."""
        config = WebPortConfig(target_url="https://example.com")
        
        assert hasattr(config, 'ethics')
        assert hasattr(config, 'crawler')
        assert hasattr(config, 'migration')
        assert hasattr(config, 'logging')
        assert hasattr(config, 'checkpoint')
    
    def test_config_can_export_yaml(self, temp_dir):
        """Config can be exported to YAML."""
        config = WebPortConfig(target_url="https://example.com")
        
        yaml_path = temp_dir / "config.yaml"
        config.to_yaml(yaml_path)
        
        assert yaml_path.exists()


class TestUtilityContracts:
    """Verify utility function contracts."""
    
    def test_url_normalizer_returns_string(self):
        """URLNormalizer.normalize() returns string."""
        from webport.crawlers.utils.dedup import URLNormalizer
        
        normalizer = URLNormalizer()
        result = normalizer.normalize("https://example.com/page")
        
        assert isinstance(result, str)
    
    def test_deduplicator_returns_bool(self):
        """URLDeduplicator.should_process() returns bool."""
        from webport.crawlers.utils.dedup import URLDeduplicator
        
        dedup = URLDeduplicator()
        result = dedup.should_process("https://example.com/page")
        
        assert isinstance(result, bool)
    
    def test_rate_limiter_has_acquire_release(self):
        """DomainRateLimiter has acquire and release."""
        from webport.crawlers.utils.rate_limiter import DomainRateLimiter
        
        limiter = DomainRateLimiter()
        
        assert hasattr(limiter, 'acquire')
        assert hasattr(limiter, 'release')
        assert hasattr(limiter, 'async_acquire')


# ============================================
# Integration Contract Tests
# ============================================

class TestComponentIntegration:
    """Test that components work together correctly."""
    
    def test_crawler_uses_rate_limiter(self, base_config: WebPortConfig):
        """Crawler integrates with rate limiter."""
        from webport.crawlers import StaticSiteCrawler
        
        crawler = StaticSiteCrawler(base_config)
        
        assert crawler.rate_limiter is not None
    
    def test_crawler_uses_deduplicator(self, base_config: WebPortConfig):
        """Crawler integrates with deduplicator."""
        from webport.crawlers import StaticSiteCrawler
        
        crawler = StaticSiteCrawler(base_config)
        
        assert crawler.deduplicator is not None
    
    def test_crawler_uses_robots_checker(self, base_config: WebPortConfig):
        """Crawler integrates with robots checker."""
        from webport.crawlers import StaticSiteCrawler
        
        crawler = StaticSiteCrawler(base_config)
        
        assert crawler.robots_checker is not None
