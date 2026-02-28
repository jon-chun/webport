"""
WebPort Static Site Crawler

Crawler for generic static websites.
"""

from __future__ import annotations

import logging
from typing import List

from webport.core.config import WebPortConfig
from webport.core.models import CrawledPage
from webport.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class StaticSiteCrawler(BaseCrawler):
    """
    Crawler for generic static websites.
    
    Uses HTTP crawling with link extraction.
    """
    
    def __init__(self, config: WebPortConfig):
        super().__init__(config)
    
    async def crawl(self) -> List[CrawledPage]:
        """Crawl static site."""
        logger.info(f"Starting static site crawl of {self.base_url}")
        return await super().crawl()
    
    async def _process_page(self, page: CrawledPage) -> None:
        """Process a crawled page."""
        # Extract additional metadata specific to static sites
        pass


__all__ = ["StaticSiteCrawler"]
