"""
WebPort Main Class

High-level API for the WebPort toolkit.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from webport.core.config import MigrationTarget, SiteType, WebPortConfig
from webport.core.logger import setup_logging
from webport.core.metrics import MetricsCollector
from webport.core.models import CrawlResult, MigrationResult
from webport.core.shutdown import get_shutdown_manager, graceful_shutdown
from webport.crawlers import BaseCrawler, StaticSiteCrawler, WordPressCrawler
from webport.crawlers.utils.health import check_site_health
from webport.migrators.base import BaseMigrator
from webport.migrators.nextjs import NextJSMigrator
from webport.utils.notifications import NotificationManager, NotificationLevel

logger = logging.getLogger(__name__)


class WebPort:
    """
    Main WebPort class providing high-level API.
    
    Example:
        >>> config = WebPortConfig(target_url="https://example.com")
        >>> forge = WebPort(config)
        >>> result = await forge.run()
    """
    
    CRAWLERS: Dict[SiteType, Type[BaseCrawler]] = {
        SiteType.WORDPRESS: WordPressCrawler,
        SiteType.STATIC: StaticSiteCrawler,
        SiteType.AUTO: StaticSiteCrawler,  # Default
    }
    
    MIGRATORS: Dict[MigrationTarget, Type[BaseMigrator]] = {
        MigrationTarget.NEXTJS: NextJSMigrator,
        # MigrationTarget.GATSBY: GatsbyMigrator,
        # MigrationTarget.ASTRO: AstroMigrator,
    }
    
    def __init__(self, config: WebPortConfig):
        self.config = config
        self._setup_logging()
        
        self.metrics = MetricsCollector()
        self.notifications = NotificationManager(config.notifications)
        self._shutdown_manager = get_shutdown_manager()
        
        # Results
        self.crawl_result: Optional[CrawlResult] = None
        self.migration_result: Optional[MigrationResult] = None
    
    def _setup_logging(self) -> None:
        """Setup logging based on config."""
        setup_logging(
            level=self.config.logging.level,
            format=self.config.logging.format.value,
            file=self.config.logging.file,
            module_levels=self.config.logging.module_levels,
        )
    
    async def run(
        self,
        crawl: bool = True,
        analyze: bool = True,
        migrate: bool = False,
        target: Optional[str] = None,
    ) -> CrawlResult:
        """
        Run the WebPort pipeline.
        
        Args:
            crawl: Whether to crawl the site
            analyze: Whether to analyze the crawled data
            migrate: Whether to generate migration output
            target: Migration target framework (if migrate=True)
            
        Returns:
            CrawlResult with all extracted data
        """
        start_time = datetime.utcnow()
        
        with graceful_shutdown():
            try:
                # Health check
                logger.info(f"Running health check on {self.config.target_url}")
                health = await check_site_health(self.config.target_url)
                
                if not health.can_crawl:
                    logger.error(f"Health check failed: {health.overall_status}")
                    raise RuntimeError(f"Site cannot be crawled: {health.overall_status}")
                
                # Detect site type
                site_type = await self._detect_site_type()
                logger.info(f"Detected site type: {site_type.value}")
                
                # Crawl
                if crawl:
                    self.crawl_result = await self._crawl(site_type)
                
                # Analyze
                if analyze and self.crawl_result:
                    await self._analyze()
                
                # Migrate
                if migrate and self.crawl_result:
                    target_enum = MigrationTarget(target or self.config.migration.target.value)
                    self.migration_result = await self._migrate(target_enum)
                
                # Notify success
                if self.config.notifications.notify_on_complete:
                    await self.notifications.notify_crawl_complete(
                        url=self.config.target_url,
                        pages_crawled=len(self.crawl_result.pages) if self.crawl_result else 0,
                        duration_seconds=(datetime.utcnow() - start_time).total_seconds(),
                    )
                
                return self.crawl_result
                
            except Exception as e:
                logger.error(f"Pipeline failed: {e}")
                
                if self.config.notifications.notify_on_error:
                    await self.notifications.notify_crawl_error(
                        url=self.config.target_url,
                        error=str(e),
                    )
                
                raise
    
    async def _detect_site_type(self) -> SiteType:
        """Auto-detect site type."""
        if self.config.site_type != SiteType.AUTO:
            return self.config.site_type
        
        # Check for WordPress
        try:
            crawler = WordPressCrawler(self.config)
            if await crawler.detect_wordpress():
                return SiteType.WORDPRESS
        except Exception:
            pass
        
        return SiteType.STATIC
    
    async def _crawl(self, site_type: SiteType) -> CrawlResult:
        """Execute crawl."""
        logger.info(f"Starting crawl with {site_type.value} crawler")
        
        crawler_class = self.CRAWLERS.get(site_type, StaticSiteCrawler)
        crawler = crawler_class(self.config)
        
        start = datetime.utcnow()
        pages = await crawler.crawl()
        duration = (datetime.utcnow() - start).total_seconds()
        
        result = CrawlResult(
            target_url=self.config.target_url,
            site_type=site_type.value,
            crawl_id=f"crawl_{int(start.timestamp())}",
            started_at=start,
            completed_at=datetime.utcnow(),
            duration_seconds=duration,
            pages_crawled=len(pages),
            pages=pages,
            output_path=str(self.config.output_dir),
        )
        
        # Add WordPress-specific data
        if isinstance(crawler, WordPressCrawler):
            result.posts = crawler.posts
        
        logger.info(f"Crawl complete: {len(pages)} pages in {duration:.1f}s")
        
        return result
    
    async def _analyze(self) -> None:
        """Analyze crawled data."""
        logger.info("Analyzing crawled data...")
        
        if not self.crawl_result:
            return
        
        # TODO: Implement analyzers
        pass
    
    async def _migrate(self, target: MigrationTarget) -> MigrationResult:
        """Generate migration output."""
        logger.info(f"Generating {target.value} project...")
        
        if not self.crawl_result:
            raise RuntimeError("No crawl data to migrate")
        
        migrator_class = self.MIGRATORS.get(target)
        
        if not migrator_class:
            raise ValueError(f"No migrator available for {target.value}")
        
        migrator = migrator_class(
            crawl_result=self.crawl_result,
            output_dir=self.config.output_dir / target.value,
            config=self.config.migration,
        )
        
        return await migrator.migrate()
    
    async def crawl_only(self) -> CrawlResult:
        """Run crawl only."""
        return await self.run(crawl=True, analyze=False, migrate=False)
    
    async def full_pipeline(self, target: str = "nextjs") -> MigrationResult:
        """Run full pipeline including migration."""
        await self.run(crawl=True, analyze=True, migrate=True, target=target)
        return self.migration_result


__all__ = ["WebPort"]
