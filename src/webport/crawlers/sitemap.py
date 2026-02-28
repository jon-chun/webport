"""
WebPort Sitemap Parser

Parses sitemap.xml and sitemap index files.

Addresses Critique #11: Missing Sitemap Parsing
"""

from __future__ import annotations

import gzip
import io
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import AsyncIterator, Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

import httpx

logger = logging.getLogger(__name__)


class ChangeFrequency(str, Enum):
    """Sitemap change frequency."""
    ALWAYS = "always"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    NEVER = "never"


@dataclass
class SitemapURL:
    """A URL from sitemap."""
    
    loc: str
    lastmod: Optional[datetime] = None
    changefreq: Optional[ChangeFrequency] = None
    priority: Optional[float] = None
    images: List[str] = field(default_factory=list)
    videos: List[Dict] = field(default_factory=list)
    news: Optional[Dict] = None
    
    @property
    def is_fresh(self) -> bool:
        """Check if URL was recently modified."""
        if not self.lastmod:
            return True  # Unknown, assume fresh
        return (datetime.utcnow() - self.lastmod).days < 30


@dataclass
class Sitemap:
    """A sitemap or sitemap index."""
    
    url: str
    is_index: bool = False
    urls: List[SitemapURL] = field(default_factory=list)
    sitemaps: List[str] = field(default_factory=list)  # For sitemap indexes
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    
    @property
    def url_count(self) -> int:
        return len(self.urls)


class SitemapParser:
    """XML sitemap parser."""
    
    SITEMAP_NS = {
        "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "image": "http://www.google.com/schemas/sitemap-image/1.1",
        "video": "http://www.google.com/schemas/sitemap-video/1.1",
        "news": "http://www.google.com/schemas/sitemap-news/0.9",
    }
    
    def parse(self, content: str, url: str) -> Sitemap:
        """Parse sitemap XML content."""
        sitemap = Sitemap(url=url)
        
        try:
            # Remove BOM and fix encoding issues
            content = content.strip()
            if content.startswith('\ufeff'):
                content = content[1:]
            
            root = ET.fromstring(content)
            
            # Detect namespace
            ns_match = re.match(r'\{([^}]+)\}', root.tag)
            ns = ns_match.group(1) if ns_match else self.SITEMAP_NS["sm"]
            
            # Check if this is a sitemap index
            if root.tag.endswith("sitemapindex"):
                sitemap.is_index = True
                sitemap.sitemaps = self._parse_sitemap_index(root, ns)
            else:
                sitemap.urls = self._parse_urlset(root, ns)
            
        except ET.ParseError as e:
            sitemap.error = f"XML parse error: {e}"
            logger.error(f"Failed to parse sitemap {url}: {e}")
        except Exception as e:
            sitemap.error = str(e)
            logger.error(f"Failed to parse sitemap {url}: {e}")
        
        return sitemap
    
    def _parse_sitemap_index(self, root: ET.Element, ns: str) -> List[str]:
        """Parse sitemap index."""
        sitemaps = []
        
        for sitemap_elem in root.findall(f".//{{{ns}}}sitemap"):
            loc = sitemap_elem.find(f"{{{ns}}}loc")
            if loc is not None and loc.text:
                sitemaps.append(loc.text.strip())
        
        return sitemaps
    
    def _parse_urlset(self, root: ET.Element, ns: str) -> List[SitemapURL]:
        """Parse URL set."""
        urls = []
        
        for url_elem in root.findall(f".//{{{ns}}}url"):
            url = self._parse_url_element(url_elem, ns)
            if url:
                urls.append(url)
        
        return urls
    
    def _parse_url_element(self, elem: ET.Element, ns: str) -> Optional[SitemapURL]:
        """Parse single URL element."""
        loc = elem.find(f"{{{ns}}}loc")
        if loc is None or not loc.text:
            return None
        
        url = SitemapURL(loc=loc.text.strip())
        
        # Last modified
        lastmod = elem.find(f"{{{ns}}}lastmod")
        if lastmod is not None and lastmod.text:
            url.lastmod = self._parse_date(lastmod.text.strip())
        
        # Change frequency
        changefreq = elem.find(f"{{{ns}}}changefreq")
        if changefreq is not None and changefreq.text:
            try:
                url.changefreq = ChangeFrequency(changefreq.text.strip().lower())
            except ValueError:
                pass
        
        # Priority
        priority = elem.find(f"{{{ns}}}priority")
        if priority is not None and priority.text:
            try:
                url.priority = float(priority.text.strip())
            except ValueError:
                pass
        
        # Images
        for img in elem.findall(f".//{{{self.SITEMAP_NS['image']}}}image"):
            img_loc = img.find(f"{{{self.SITEMAP_NS['image']}}}loc")
            if img_loc is not None and img_loc.text:
                url.images.append(img_loc.text.strip())
        
        return url
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from various formats."""
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
        ]
        
        # Handle timezone offset format
        date_str = re.sub(r'(\d{2}):(\d{2})$', r'\1\2', date_str)
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None


class SitemapFetcher:
    """Fetches and parses sitemaps."""
    
    COMMON_SITEMAP_PATHS = [
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/sitemap/sitemap.xml",
        "/sitemaps/sitemap.xml",
        "/wp-sitemap.xml",  # WordPress
        "/sitemap.xml.gz",
    ]
    
    def __init__(
        self,
        user_agent: str = "WebPort/1.0",
        timeout: float = 30.0,
        max_sitemaps: int = 100,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_sitemaps = max_sitemaps
        self._parser = SitemapParser()
    
    async def discover_sitemaps(self, base_url: str) -> List[str]:
        """Discover sitemap URLs for a site."""
        discovered = []
        
        # Check common paths
        async with httpx.AsyncClient() as client:
            for path in self.COMMON_SITEMAP_PATHS:
                url = urljoin(base_url, path)
                try:
                    response = await client.head(
                        url,
                        timeout=5,
                        follow_redirects=True,
                        headers={"User-Agent": self.user_agent},
                    )
                    if response.status_code == 200:
                        discovered.append(url)
                except Exception:
                    pass
        
        return discovered
    
    async def fetch_sitemap(self, url: str) -> Sitemap:
        """Fetch and parse a single sitemap."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    timeout=self.timeout,
                    follow_redirects=True,
                    headers={"User-Agent": self.user_agent},
                )
                
                if response.status_code != 200:
                    return Sitemap(url=url, error=f"HTTP {response.status_code}")
                
                # Handle gzipped content
                content = response.content
                if url.endswith(".gz") or response.headers.get("content-encoding") == "gzip":
                    try:
                        content = gzip.decompress(content)
                    except Exception:
                        pass
                
                if isinstance(content, bytes):
                    content = content.decode("utf-8", errors="ignore")
                
                return self._parser.parse(content, url)
                
        except Exception as e:
            logger.error(f"Failed to fetch sitemap {url}: {e}")
            return Sitemap(url=url, error=str(e))
    
    async def fetch_all_urls(
        self,
        base_url: str,
        sitemap_urls: Optional[List[str]] = None,
    ) -> AsyncIterator[SitemapURL]:
        """Fetch all URLs from all sitemaps."""
        visited_sitemaps: Set[str] = set()
        sitemaps_to_fetch: List[str] = []
        
        # Start with provided sitemaps or discover
        if sitemap_urls:
            sitemaps_to_fetch.extend(sitemap_urls)
        else:
            sitemaps_to_fetch.extend(await self.discover_sitemaps(base_url))
        
        while sitemaps_to_fetch and len(visited_sitemaps) < self.max_sitemaps:
            url = sitemaps_to_fetch.pop(0)
            
            if url in visited_sitemaps:
                continue
            
            visited_sitemaps.add(url)
            
            logger.info(f"Fetching sitemap: {url}")
            sitemap = await self.fetch_sitemap(url)
            
            if sitemap.error:
                logger.warning(f"Sitemap error for {url}: {sitemap.error}")
                continue
            
            # If it's an index, add child sitemaps to queue
            if sitemap.is_index:
                sitemaps_to_fetch.extend(sitemap.sitemaps)
            else:
                # Yield URLs
                for sitemap_url in sitemap.urls:
                    yield sitemap_url
    
    async def get_all_urls(
        self,
        base_url: str,
        sitemap_urls: Optional[List[str]] = None,
        fresh_only: bool = False,
    ) -> List[str]:
        """Get all URLs from sitemaps as a list."""
        urls = []
        async for url in self.fetch_all_urls(base_url, sitemap_urls):
            if fresh_only and not url.is_fresh:
                continue
            urls.append(url.loc)
        return urls


_sitemap_fetcher: Optional[SitemapFetcher] = None


def get_sitemap_fetcher() -> SitemapFetcher:
    """Get global sitemap fetcher."""
    global _sitemap_fetcher
    if _sitemap_fetcher is None:
        _sitemap_fetcher = SitemapFetcher()
    return _sitemap_fetcher


__all__ = [
    "ChangeFrequency",
    "SitemapURL",
    "Sitemap",
    "SitemapParser",
    "SitemapFetcher",
    "get_sitemap_fetcher",
]
