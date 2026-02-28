"""
WebPort Sitemap Parser

XML sitemap parsing with support for sitemap indexes.

Addresses Critique #11: sitemap.xml Parser Not Implemented
"""

from __future__ import annotations

import asyncio
import gzip
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


class SitemapType(Enum):
    URLSET = "urlset"
    INDEX = "sitemapindex"
    RSS = "rss"
    ATOM = "atom"
    TEXT = "text"
    UNKNOWN = "unknown"


@dataclass
class SitemapURL:
    """A URL entry from a sitemap."""
    loc: str
    lastmod: Optional[datetime] = None
    changefreq: Optional[str] = None
    priority: Optional[float] = None
    images: List[str] = field(default_factory=list)
    videos: List[Dict] = field(default_factory=list)
    news: Optional[Dict] = None
    alternates: Dict[str, str] = field(default_factory=dict)


@dataclass
class Sitemap:
    """A parsed sitemap."""
    url: str
    sitemap_type: SitemapType
    urls: List[SitemapURL] = field(default_factory=list)
    sitemaps: List[str] = field(default_factory=list)
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    
    @property
    def url_count(self) -> int:
        return len(self.urls)


class SitemapParser:
    """Parse various sitemap formats."""
    
    NAMESPACES = {
        "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
        "image": "http://www.google.com/schemas/sitemap-image/1.1",
        "video": "http://www.google.com/schemas/sitemap-video/1.1",
        "news": "http://www.google.com/schemas/sitemap-news/0.9",
        "xhtml": "http://www.w3.org/1999/xhtml",
    }
    
    def detect_type(self, content: str) -> SitemapType:
        content_lower = content[:1000].lower()
        
        if "<sitemapindex" in content_lower:
            return SitemapType.INDEX
        if "<urlset" in content_lower:
            return SitemapType.URLSET
        if "<rss" in content_lower:
            return SitemapType.RSS
        if "<feed" in content_lower:
            return SitemapType.ATOM
        if content.strip() and all(
            line.strip().startswith("http") for line in content.strip().split("\n")[:5]
        ):
            return SitemapType.TEXT
        
        return SitemapType.UNKNOWN
    
    def parse(self, content: str, url: str) -> Sitemap:
        sitemap_type = self.detect_type(content)
        
        try:
            if sitemap_type == SitemapType.URLSET:
                return self._parse_urlset(content, url)
            elif sitemap_type == SitemapType.INDEX:
                return self._parse_index(content, url)
            elif sitemap_type == SitemapType.RSS:
                return self._parse_rss(content, url)
            elif sitemap_type == SitemapType.ATOM:
                return self._parse_atom(content, url)
            elif sitemap_type == SitemapType.TEXT:
                return self._parse_text(content, url)
            else:
                return Sitemap(url=url, sitemap_type=SitemapType.UNKNOWN, 
                              error="Unknown sitemap format")
        except Exception as e:
            logger.error(f"Error parsing sitemap {url}: {e}")
            return Sitemap(url=url, sitemap_type=sitemap_type, error=str(e))
    
    def _parse_urlset(self, content: str, url: str) -> Sitemap:
        sitemap = Sitemap(url=url, sitemap_type=SitemapType.URLSET)
        
        root = ET.fromstring(content)
        ns = self.NAMESPACES
        
        for url_elem in root.findall(".//sm:url", ns) or root.findall(".//url"):
            sitemap_url = SitemapURL(loc="")
            
            loc = url_elem.find("sm:loc", ns) or url_elem.find("loc")
            if loc is not None and loc.text:
                sitemap_url.loc = loc.text.strip()
            else:
                continue
            
            lastmod = url_elem.find("sm:lastmod", ns) or url_elem.find("lastmod")
            if lastmod is not None and lastmod.text:
                sitemap_url.lastmod = self._parse_date(lastmod.text)
            
            changefreq = url_elem.find("sm:changefreq", ns) or url_elem.find("changefreq")
            if changefreq is not None and changefreq.text:
                sitemap_url.changefreq = changefreq.text.strip()
            
            priority = url_elem.find("sm:priority", ns) or url_elem.find("priority")
            if priority is not None and priority.text:
                try:
                    sitemap_url.priority = float(priority.text)
                except ValueError:
                    pass
            
            for img in url_elem.findall(".//image:loc", ns):
                if img.text:
                    sitemap_url.images.append(img.text.strip())
            
            for link in url_elem.findall(".//xhtml:link[@rel='alternate']", ns):
                hreflang = link.get("hreflang")
                href = link.get("href")
                if hreflang and href:
                    sitemap_url.alternates[hreflang] = href
            
            sitemap.urls.append(sitemap_url)
        
        return sitemap
    
    def _parse_index(self, content: str, url: str) -> Sitemap:
        sitemap = Sitemap(url=url, sitemap_type=SitemapType.INDEX)
        
        root = ET.fromstring(content)
        ns = self.NAMESPACES
        
        for sm_elem in root.findall(".//sm:sitemap", ns) or root.findall(".//sitemap"):
            loc = sm_elem.find("sm:loc", ns) or sm_elem.find("loc")
            if loc is not None and loc.text:
                sitemap.sitemaps.append(loc.text.strip())
        
        return sitemap
    
    def _parse_rss(self, content: str, url: str) -> Sitemap:
        sitemap = Sitemap(url=url, sitemap_type=SitemapType.RSS)
        
        root = ET.fromstring(content)
        
        for item in root.findall(".//item"):
            link = item.find("link")
            if link is not None and link.text:
                sitemap_url = SitemapURL(loc=link.text.strip())
                
                pubdate = item.find("pubDate")
                if pubdate is not None and pubdate.text:
                    sitemap_url.lastmod = self._parse_date(pubdate.text)
                
                sitemap.urls.append(sitemap_url)
        
        return sitemap
    
    def _parse_atom(self, content: str, url: str) -> Sitemap:
        sitemap = Sitemap(url=url, sitemap_type=SitemapType.ATOM)
        
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(content)
        
        for entry in root.findall(".//atom:entry", ns) or root.findall(".//entry"):
            link = entry.find("atom:link[@rel='alternate']", ns) or entry.find("link")
            href = link.get("href") if link is not None else None
            
            if href:
                sitemap_url = SitemapURL(loc=href)
                
                updated = entry.find("atom:updated", ns) or entry.find("updated")
                if updated is not None and updated.text:
                    sitemap_url.lastmod = self._parse_date(updated.text)
                
                sitemap.urls.append(sitemap_url)
        
        return sitemap
    
    def _parse_text(self, content: str, url: str) -> Sitemap:
        sitemap = Sitemap(url=url, sitemap_type=SitemapType.TEXT)
        
        for line in content.strip().split("\n"):
            line = line.strip()
            if line and line.startswith("http"):
                sitemap.urls.append(SitemapURL(loc=line))
        
        return sitemap
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        formats = [
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
        ]
        
        date_str = date_str.strip()
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        
        return None


class SitemapFetcher:
    """
    Fetch and parse sitemaps with support for:
    - Sitemap indexes
    - Gzipped sitemaps
    - Common sitemap locations
    """
    
    COMMON_PATHS = [
        "/sitemap.xml",
        "/sitemap_index.xml",
        "/sitemap-index.xml",
        "/sitemaps.xml",
        "/sitemap1.xml",
        "/post-sitemap.xml",
        "/page-sitemap.xml",
        "/wp-sitemap.xml",
    ]
    
    def __init__(self, user_agent: str = "WebPort/1.0", timeout: float = 30.0):
        self.user_agent = user_agent
        self.timeout = timeout
        self._parser = SitemapParser()
    
    async def fetch(self, url: str) -> Sitemap:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    url,
                    headers={"User-Agent": self.user_agent},
                    follow_redirects=True,
                )
                
                if response.status_code != 200:
                    return Sitemap(
                        url=url,
                        sitemap_type=SitemapType.UNKNOWN,
                        error=f"HTTP {response.status_code}"
                    )
                
                content = response.content
                
                if url.endswith(".gz") or response.headers.get("content-encoding") == "gzip":
                    try:
                        content = gzip.decompress(content)
                    except Exception:
                        pass
                
                text = content.decode("utf-8", errors="ignore")
                return self._parser.parse(text, url)
                
        except Exception as e:
            logger.error(f"Error fetching sitemap {url}: {e}")
            return Sitemap(url=url, sitemap_type=SitemapType.UNKNOWN, error=str(e))
    
    async def fetch_all(self, base_url: str, known_sitemaps: Optional[List[str]] = None) -> List[Sitemap]:
        sitemaps: List[Sitemap] = []
        processed: Set[str] = set()
        to_process: List[str] = []
        
        if known_sitemaps:
            to_process.extend(known_sitemaps)
        else:
            parsed = urlparse(base_url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            to_process.extend(urljoin(base, path) for path in self.COMMON_PATHS)
        
        while to_process:
            url = to_process.pop(0)
            if url in processed:
                continue
            processed.add(url)
            
            sitemap = await self.fetch(url)
            
            if sitemap.error:
                continue
            
            sitemaps.append(sitemap)
            logger.info(f"Parsed sitemap {url}: {sitemap.url_count} URLs")
            
            for child_url in sitemap.sitemaps:
                if child_url not in processed:
                    to_process.append(child_url)
        
        return sitemaps
    
    async def get_all_urls(self, base_url: str, 
                          known_sitemaps: Optional[List[str]] = None) -> AsyncIterator[SitemapURL]:
        sitemaps = await self.fetch_all(base_url, known_sitemaps)
        seen: Set[str] = set()
        
        for sitemap in sitemaps:
            for url in sitemap.urls:
                if url.loc not in seen:
                    seen.add(url.loc)
                    yield url


__all__ = [
    "SitemapType",
    "SitemapURL",
    "Sitemap",
    "SitemapParser",
    "SitemapFetcher",
]
