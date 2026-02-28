"""
WebPort Robots.txt Parser

Full robots.txt parsing with caching.

Addresses Critique #12: robots.txt Parser Not Implemented
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)


@dataclass
class RobotsRule:
    """A single robots.txt rule."""
    pattern: str
    allowed: bool
    specificity: int = 0
    
    def __post_init__(self):
        self.specificity = len(self.pattern)
        self._regex = self._compile_pattern(self.pattern)
    
    def _compile_pattern(self, pattern: str) -> re.Pattern:
        regex = re.escape(pattern)
        regex = regex.replace(r"\*", ".*")
        regex = regex.replace(r"\$", "$")
        if not regex.endswith("$"):
            regex += ".*"
        return re.compile(f"^{regex}", re.IGNORECASE)
    
    def matches(self, path: str) -> bool:
        return bool(self._regex.match(path))


@dataclass
class RobotsDirectives:
    """Directives for a user agent."""
    user_agent: str
    rules: List[RobotsRule] = field(default_factory=list)
    crawl_delay: Optional[float] = None
    sitemaps: List[str] = field(default_factory=list)
    
    def is_allowed(self, path: str) -> bool:
        matching_rules = [r for r in self.rules if r.matches(path)]
        if not matching_rules:
            return True
        most_specific = max(matching_rules, key=lambda r: r.specificity)
        return most_specific.allowed


@dataclass
class RobotsData:
    """Parsed robots.txt data."""
    url: str
    directives: Dict[str, RobotsDirectives] = field(default_factory=dict)
    sitemaps: List[str] = field(default_factory=list)
    fetched_at: float = field(default_factory=time.time)
    ttl: int = 86400
    status_code: Optional[int] = None
    error: Optional[str] = None
    
    @property
    def is_expired(self) -> bool:
        return (time.time() - self.fetched_at) > self.ttl
    
    def get_directives(self, user_agent: str) -> RobotsDirectives:
        ua_lower = user_agent.lower()
        for ua, directives in self.directives.items():
            if ua.lower() in ua_lower or ua == "*":
                return directives
        if "*" in self.directives:
            return self.directives["*"]
        return RobotsDirectives(user_agent="*")
    
    def is_allowed(self, path: str, user_agent: str = "*") -> bool:
        if self.error or self.status_code == 404:
            return True
        if self.status_code and self.status_code >= 500:
            return False
        return self.get_directives(user_agent).is_allowed(path)
    
    def get_crawl_delay(self, user_agent: str = "*") -> Optional[float]:
        return self.get_directives(user_agent).crawl_delay


class RobotsParser:
    """Parse robots.txt content."""
    
    def parse(self, content: str, url: str) -> RobotsData:
        data = RobotsData(url=url)
        current_agents: List[str] = []
        
        for line in content.split("\n"):
            line = line.split("#")[0].strip()
            if not line:
                continue
            
            if ":" not in line:
                continue
            
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            
            if key == "user-agent":
                if current_agents and any(
                    ua in data.directives for ua in current_agents
                ):
                    current_agents = []
                current_agents.append(value)
                if value not in data.directives:
                    data.directives[value] = RobotsDirectives(user_agent=value)
            
            elif key == "disallow" and current_agents:
                if value:
                    for ua in current_agents:
                        data.directives[ua].rules.append(
                            RobotsRule(pattern=value, allowed=False)
                        )
            
            elif key == "allow" and current_agents:
                if value:
                    for ua in current_agents:
                        data.directives[ua].rules.append(
                            RobotsRule(pattern=value, allowed=True)
                        )
            
            elif key == "crawl-delay" and current_agents:
                try:
                    delay = float(value)
                    for ua in current_agents:
                        data.directives[ua].crawl_delay = delay
                except ValueError:
                    pass
            
            elif key == "sitemap":
                if value not in data.sitemaps:
                    data.sitemaps.append(value)
        
        return data


class RobotsChecker:
    """
    Robots.txt checker with caching.
    
    Example:
        >>> checker = RobotsChecker()
        >>> if await checker.is_allowed("https://example.com/page"):
        ...     # crawl the page
    """
    
    def __init__(
        self,
        user_agent: str = "WebPort/1.0",
        respect_robots: bool = True,
        cache_ttl: int = 86400,
    ):
        self.user_agent = user_agent
        self.respect_robots = respect_robots
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, RobotsData] = {}
        self._parser = RobotsParser()
        self._locks: Dict[str, asyncio.Lock] = {}
    
    def _get_robots_url(self, url: str) -> str:
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    
    def _get_path(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path or "/"
        if parsed.query:
            path += f"?{parsed.query}"
        return path
    
    async def _fetch_robots(self, robots_url: str) -> RobotsData:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    robots_url,
                    headers={"User-Agent": self.user_agent},
                    follow_redirects=True,
                )
                
                if response.status_code == 200:
                    data = self._parser.parse(response.text, robots_url)
                    data.status_code = response.status_code
                    return data
                else:
                    return RobotsData(
                        url=robots_url,
                        status_code=response.status_code,
                    )
        except Exception as e:
            logger.warning(f"Failed to fetch {robots_url}: {e}")
            return RobotsData(url=robots_url, error=str(e))
    
    async def get_robots(self, url: str) -> RobotsData:
        robots_url = self._get_robots_url(url)
        
        if robots_url in self._cache:
            cached = self._cache[robots_url]
            if not cached.is_expired:
                return cached
        
        if robots_url not in self._locks:
            self._locks[robots_url] = asyncio.Lock()
        
        async with self._locks[robots_url]:
            if robots_url in self._cache and not self._cache[robots_url].is_expired:
                return self._cache[robots_url]
            
            data = await self._fetch_robots(robots_url)
            data.ttl = self.cache_ttl
            self._cache[robots_url] = data
            
            if data.sitemaps:
                logger.info(f"Found {len(data.sitemaps)} sitemaps in robots.txt")
            
            return data
    
    async def is_allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        
        robots = await self.get_robots(url)
        path = self._get_path(url)
        return robots.is_allowed(path, self.user_agent)
    
    async def get_crawl_delay(self, url: str) -> Optional[float]:
        if not self.respect_robots:
            return None
        
        robots = await self.get_robots(url)
        return robots.get_crawl_delay(self.user_agent)
    
    async def get_sitemaps(self, url: str) -> List[str]:
        robots = await self.get_robots(url)
        return robots.sitemaps
    
    def clear_cache(self) -> None:
        self._cache.clear()


__all__ = [
    "RobotsRule",
    "RobotsDirectives",
    "RobotsData",
    "RobotsParser",
    "RobotsChecker",
]
