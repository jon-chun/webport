"""
WebPort Base Crawler

Abstract base class for all crawlers.
"""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from webport.core.checkpoint import CheckpointManager, CrawlCheckpoint, compute_content_hash
from webport.core.config import CrawlerConfig, EthicsConfig, WebPortConfig
from webport.core.exceptions import (
    CrawlerError,
    HTTPError,
    MaxDepthExceededError,
    MaxPagesExceededError,
    NetworkError,
    RateLimitError,
    RobotsBlockedError,
)
from webport.core.metrics import CrawlMetrics, MetricsCollector
from webport.core.models import CrawledPage, PageContent, PageMetadata
from webport.core.retry import with_async_retry, get_circuit_manager
from webport.core.shutdown import get_shutdown_manager
from webport.crawlers.utils.dedup import URLDeduplicator
from webport.crawlers.utils.rate_limiter import DomainRateLimiter, RateLimitConfig
from webport.crawlers.utils.robots import RobotsChecker
from webport.crawlers.utils.sitemap import SitemapFetcher

logger = logging.getLogger(__name__)


@dataclass
class CrawlContext:
    """Context for a crawl operation."""
    
    config: WebPortConfig
    checkpoint: CrawlCheckpoint
    metrics: CrawlMetrics
    deduplicator: URLDeduplicator
    rate_limiter: DomainRateLimiter
    robots_checker: RobotsChecker
    sitemap_fetcher: SitemapFetcher
    
    # State
    pages: List[CrawledPage] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    # Callbacks
    on_page_crawled: Optional[Callable[[CrawledPage], None]] = None
    on_error: Optional[Callable[[str, Exception], None]] = None


class BaseCrawler(ABC):
    """
    Abstract base class for crawlers.
    
    Provides common functionality:
    - Rate limiting
    - robots.txt checking
    - Deduplication
    - Checkpointing
    - Metrics collection
    """
    
    def __init__(self, config: WebPortConfig):
        self.config = config
        self.base_url = config.target_url
        self._parsed_base = urlparse(self.base_url)
        
        # Initialize utilities
        self.rate_limiter = DomainRateLimiter(RateLimitConfig(
            requests_per_second=config.ethics.rate_limit,
            burst_size=config.ethics.burst_size,
            concurrent_requests=config.ethics.max_concurrent,
        ))
        
        self.robots_checker = RobotsChecker(
            user_agent=config.ethics.user_agent,
            respect_robots=config.ethics.respect_robots_txt,
        )
        
        self.deduplicator = URLDeduplicator()
        self.sitemap_fetcher = SitemapFetcher(user_agent=config.ethics.user_agent)
        self.checkpoint_manager = CheckpointManager(
            checkpoint_dir=config.checkpoint.directory,
            auto_save_interval=config.checkpoint.auto_save_interval,
        )
        
        self.metrics = MetricsCollector()
        self._client: Optional[httpx.AsyncClient] = None
        self._shutdown_manager = get_shutdown_manager()
    
    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.config.crawler.timeout,
                follow_redirects=self.config.crawler.follow_redirects,
                verify=self.config.crawler.verify_ssl,
                headers={"User-Agent": self.config.ethics.user_agent},
            )
        return self._client
    
    async def close(self) -> None:
        """Close resources."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    async def crawl(self) -> List[CrawledPage]:
        """
        Execute the crawl.
        
        Returns:
            List of crawled pages
        """
        logger.info(f"Starting crawl of {self.base_url}")
        
        # Get or resume checkpoint
        checkpoint = self.checkpoint_manager.get_or_create(
            target_url=self.base_url,
            force_new=False,
        )
        
        # Start metrics
        self.metrics.start()
        
        # Register shutdown callback
        @self._shutdown_manager.on_shutdown(priority=10)
        def save_checkpoint():
            self.checkpoint_manager.save()
            logger.info("Checkpoint saved on shutdown")
        
        # Start auto-save
        self.checkpoint_manager.start_auto_save()
        
        pages: List[CrawledPage] = []
        
        try:
            # Discover URLs from sitemap
            await self._discover_from_sitemap(checkpoint)
            
            # Process queue
            while checkpoint.url_queue:
                # Check shutdown
                if self._shutdown_manager.is_shutting_down:
                    break
                
                # Check limits
                if len(pages) >= self.config.crawler.max_pages:
                    logger.info(f"Reached max pages limit: {self.config.crawler.max_pages}")
                    break
                
                # Get next URL
                url_data = checkpoint.get_next_url()
                if not url_data:
                    break
                
                url, depth = url_data
                
                # Check depth
                if depth > self.config.crawler.max_depth:
                    checkpoint.mark_url_failed(url, "MaxDepthExceeded")
                    continue
                
                # Check deduplication
                is_new, normalized = self.deduplicator.add_and_check(url)
                if not is_new:
                    continue
                
                # Check robots.txt
                if not await self.robots_checker.is_allowed(url):
                    logger.debug(f"Blocked by robots.txt: {url}")
                    checkpoint.mark_url_failed(url, "RobotsBlocked")
                    continue
                
                # Crawl page
                try:
                    page = await self._crawl_page(url, depth)
                    
                    if page:
                        pages.append(page)
                        content_hash = compute_content_hash(page.content.raw_html if page.content else "")
                        checkpoint.mark_completed(url, content_hash)
                        
                        # Discover links
                        if page.content:
                            new_urls = self._extract_links(page.content.raw_html, url)
                            for new_url in new_urls:
                                if self._is_same_domain(new_url):
                                    checkpoint.add_discovered_url(new_url, depth + 1)
                        
                        # Update metrics
                        self.metrics.record_queue_depth(len(checkpoint.url_queue))
                
                except Exception as e:
                    logger.error(f"Error crawling {url}: {e}")
                    checkpoint.mark_failed(url, str(e))
            
            # Mark complete
            self.checkpoint_manager.mark_complete()
            
        finally:
            self.checkpoint_manager.stop_auto_save()
            await self.close()
        
        logger.info(f"Crawl complete: {len(pages)} pages crawled")
        return pages
    
    async def _discover_from_sitemap(self, checkpoint: CrawlCheckpoint) -> None:
        """Discover URLs from sitemap."""
        try:
            sitemaps = await self.robots_checker.get_sitemaps(self.base_url)
            
            if not sitemaps:
                # Try common sitemap locations
                sitemaps = None
            
            async for sitemap_url in self.sitemap_fetcher.get_all_urls(
                self.base_url, sitemaps
            ):
                if self._is_same_domain(sitemap_url.loc):
                    checkpoint.add_discovered_url(sitemap_url.loc, depth=1)
            
            logger.info(f"Discovered {checkpoint.progress.total_discovered} URLs from sitemaps")
            
        except Exception as e:
            logger.warning(f"Error fetching sitemaps: {e}")
    
    @with_async_retry(max_attempts=3, initial_wait=1.0, max_wait=30.0)
    async def _crawl_page(self, url: str, depth: int) -> Optional[CrawledPage]:
        """Crawl a single page."""
        start = time.perf_counter()
        
        # Rate limiting
        await self.rate_limiter.async_acquire(url, timeout=60.0)
        
        try:
            response = await self.client.get(url)
            
            duration_ms = (time.perf_counter() - start) * 1000
            
            # Record metrics
            self.metrics.record_request(
                url=url,
                status_code=response.status_code,
                bytes_size=len(response.content),
                latency_ms=duration_ms,
                success=response.status_code < 400,
            )
            
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                self.rate_limiter.record_rate_limit(url, retry_after)
                raise RateLimitError(url, retry_after)
            
            if response.status_code >= 400:
                raise HTTPError(url, response.status_code)
            
            # Parse content
            content_type = response.headers.get("content-type", "")
            
            if "text/html" not in content_type:
                return None
            
            html = response.text
            
            # Extract data
            metadata = self._extract_metadata(html, url)
            content = self._extract_content(html)
            
            return CrawledPage(
                url=url,
                final_url=str(response.url),
                status_code=response.status_code,
                content_type=content_type,
                depth=depth,
                response_time_ms=duration_ms,
                metadata=metadata,
                content=content,
            )
            
        finally:
            self.rate_limiter.release(url)
    
    def _extract_metadata(self, html: str, url: str) -> PageMetadata:
        """Extract metadata from HTML."""
        soup = BeautifulSoup(html, "lxml")
        
        metadata = PageMetadata()
        
        # Title
        title_tag = soup.find("title")
        if title_tag:
            metadata.title = title_tag.get_text(strip=True)
        
        # Meta tags
        for meta in soup.find_all("meta"):
            name = meta.get("name", "").lower()
            prop = meta.get("property", "").lower()
            content = meta.get("content", "")
            
            if name == "description" or prop == "og:description":
                metadata.description = content
            elif prop == "og:title":
                metadata.og_title = content
            elif prop == "og:image":
                metadata.og_image = content
            elif name == "author":
                metadata.author = content
            elif name == "keywords":
                metadata.keywords = [k.strip() for k in content.split(",")]
            elif name == "robots":
                metadata.robots = content
        
        # Canonical URL
        canonical = soup.find("link", rel="canonical")
        if canonical:
            metadata.canonical_url = canonical.get("href")
        
        return metadata
    
    def _extract_content(self, html: str) -> PageContent:
        """Extract content from HTML."""
        soup = BeautifulSoup(html, "lxml")
        
        # Remove script/style
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        
        text = soup.get_text(separator=" ", strip=True)
        
        # Extract headings
        headings = []
        for i in range(1, 7):
            for h in soup.find_all(f"h{i}"):
                headings.append({"level": i, "text": h.get_text(strip=True)})
        
        # Extract links
        links = []
        for a in soup.find_all("a", href=True):
            links.append({
                "href": a["href"],
                "text": a.get_text(strip=True),
            })
        
        # Extract images
        images = []
        for img in soup.find_all("img", src=True):
            images.append({
                "src": img["src"],
                "alt": img.get("alt", ""),
            })
        
        word_count = len(text.split())
        reading_time = word_count / 200  # ~200 wpm
        
        return PageContent(
            raw_html=html,
            text_content=text,
            word_count=word_count,
            reading_time_minutes=reading_time,
            headings=headings,
            links=links,
            images=images,
        )
    
    def _extract_links(self, html: str, base_url: str) -> List[str]:
        """Extract links from HTML."""
        soup = BeautifulSoup(html, "lxml")
        links = []
        
        for a in soup.find_all("a", href=True):
            href = a["href"]
            
            # Skip anchors, javascript, etc.
            if href.startswith(("#", "javascript:", "mailto:", "tel:")):
                continue
            
            # Resolve relative URLs
            absolute_url = urljoin(base_url, href)
            
            # Parse and clean
            parsed = urlparse(absolute_url)
            clean_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            
            if parsed.query:
                clean_url += f"?{parsed.query}"
            
            links.append(clean_url)
        
        return links
    
    def _is_same_domain(self, url: str) -> bool:
        """Check if URL is on the same domain."""
        parsed = urlparse(url)
        return parsed.netloc == self._parsed_base.netloc
    
    @abstractmethod
    async def _process_page(self, page: CrawledPage) -> None:
        """Process a crawled page (implemented by subclasses)."""
        pass


__all__ = [
    "BaseCrawler",
    "CrawlContext",
]
