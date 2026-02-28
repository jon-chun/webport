"""
WebPort Robots.txt Parser

Parses and enforces robots.txt rules.

Addresses Critique #12: Missing robots.txt Parser
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import httpx

logger = logging.getLogger(__name__)


@dataclass
class RobotsRule:
    """A single robots.txt rule."""
    
    path: str
    allowed: bool
    
    def matches(self, path: str) -> bool:
        """Check if path matches this rule."""
        # Handle wildcards
        pattern = self.path.replace("*", ".*").replace("$", r"\$")
        if pattern.endswith(r"\$"):
            pattern = pattern[:-2] + "$"
        else:
            pattern = f"^{pattern}"
        
        try:
            return bool(re.match(pattern, path))
        except re.error:
            return path.startswith(self.path.rstrip("*"))


@dataclass
class RobotsDirectives:
    """Directives for a user agent."""
    
    user_agent: str
    rules: List[RobotsRule] = field(default_factory=list)
    crawl_delay: Optional[float] = None
    sitemaps: List[str] = field(default_factory=list)
    
    def is_allowed(self, path: str) -> bool:
        """Check if path is allowed by these directives."""
        # Find most specific matching rule
        matching_rules = []
        for rule in self.rules:
            if rule.matches(path):
                matching_rules.append((len(rule.path), rule))
        
        if not matching_rules:
            return True  # No matching rules, allowed by default
        
        # Most specific rule wins
        matching_rules.sort(key=lambda x: x[0], reverse=True)
        return matching_rules[0][1].allowed


@dataclass
class RobotsData:
    """Parsed robots.txt data."""
    
    url: str
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    valid: bool = True
    error: Optional[str] = None
    directives: Dict[str, RobotsDirectives] = field(default_factory=dict)
    default_directives: Optional[RobotsDirectives] = None
    sitemaps: List[str] = field(default_factory=list)
    
    @property
    def is_fresh(self) -> bool:
        """Check if robots.txt is still fresh (less than 24h old)."""
        return (datetime.utcnow() - self.fetched_at) < timedelta(hours=24)
    
    def get_directives(self, user_agent: str) -> Optional[RobotsDirectives]:
        """Get directives for a specific user agent."""
        # Exact match
        ua_lower = user_agent.lower()
        if ua_lower in self.directives:
            return self.directives[ua_lower]
        
        # Partial match
        for ua, dirs in self.directives.items():
            if ua in ua_lower or ua_lower in ua:
                return dirs
        
        # Default (*)
        return self.default_directives
    
    def is_allowed(self, path: str, user_agent: str = "*") -> bool:
        """Check if path is allowed for user agent."""
        if not self.valid:
            return True  # If robots.txt couldn't be fetched, allow all
        
        directives = self.get_directives(user_agent)
        if directives is None:
            return True
        
        return directives.is_allowed(path)
    
    def get_crawl_delay(self, user_agent: str = "*") -> Optional[float]:
        """Get crawl delay for user agent."""
        directives = self.get_directives(user_agent)
        if directives:
            return directives.crawl_delay
        return None


class RobotsParser:
    """Robots.txt parser."""
    
    def parse(self, content: str, base_url: str) -> RobotsData:
        """Parse robots.txt content."""
        data = RobotsData(url=base_url)
        
        current_user_agents: List[str] = []
        current_rules: List[RobotsRule] = []
        current_crawl_delay: Optional[float] = None
        
        def save_directives():
            if current_user_agents and current_rules:
                for ua in current_user_agents:
                    ua_lower = ua.lower()
                    dirs = RobotsDirectives(
                        user_agent=ua,
                        rules=current_rules.copy(),
                        crawl_delay=current_crawl_delay,
                    )
                    if ua == "*":
                        data.default_directives = dirs
                    else:
                        data.directives[ua_lower] = dirs
        
        for line in content.split("\n"):
            line = line.strip()
            
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue
            
            # Remove inline comments
            if "#" in line:
                line = line[:line.index("#")].strip()
            
            # Parse directive
            if ":" not in line:
                continue
            
            directive, value = line.split(":", 1)
            directive = directive.strip().lower()
            value = value.strip()
            
            if directive == "user-agent":
                if current_rules:  # Save previous group
                    save_directives()
                    current_rules = []
                    current_crawl_delay = None
                
                if not current_user_agents or current_rules:
                    current_user_agents = []
                current_user_agents.append(value)
            
            elif directive == "disallow":
                if value:  # Empty disallow means allow all
                    current_rules.append(RobotsRule(path=value, allowed=False))
            
            elif directive == "allow":
                current_rules.append(RobotsRule(path=value, allowed=True))
            
            elif directive == "crawl-delay":
                try:
                    current_crawl_delay = float(value)
                except ValueError:
                    pass
            
            elif directive == "sitemap":
                data.sitemaps.append(value)
        
        # Save last group
        save_directives()
        
        return data


class RobotsManager:
    """Manages robots.txt caching and enforcement."""
    
    def __init__(
        self,
        user_agent: str = "WebPort/1.0",
        respect_robots: bool = True,
        cache_duration_hours: int = 24,
    ):
        self.user_agent = user_agent
        self.respect_robots = respect_robots
        self.cache_duration = timedelta(hours=cache_duration_hours)
        self._cache: Dict[str, RobotsData] = {}
        self._parser = RobotsParser()
    
    def _get_robots_url(self, url: str) -> str:
        """Get robots.txt URL for a given URL."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    
    async def fetch_robots(self, url: str) -> RobotsData:
        """Fetch and parse robots.txt for a URL."""
        robots_url = self._get_robots_url(url)
        domain = urlparse(url).netloc
        
        # Check cache
        if domain in self._cache:
            cached = self._cache[domain]
            if cached.is_fresh:
                return cached
        
        # Fetch robots.txt
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    robots_url,
                    timeout=10,
                    follow_redirects=True,
                    headers={"User-Agent": self.user_agent},
                )
                
                if response.status_code == 200:
                    data = self._parser.parse(response.text, robots_url)
                elif response.status_code in (404, 410):
                    # No robots.txt, allow all
                    data = RobotsData(url=robots_url, valid=True)
                else:
                    # Other error, be conservative
                    data = RobotsData(
                        url=robots_url,
                        valid=False,
                        error=f"HTTP {response.status_code}",
                    )
        except Exception as e:
            logger.warning(f"Failed to fetch robots.txt for {domain}: {e}")
            data = RobotsData(url=robots_url, valid=False, error=str(e))
        
        self._cache[domain] = data
        return data
    
    async def is_allowed(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt."""
        if not self.respect_robots:
            return True
        
        robots = await self.fetch_robots(url)
        path = urlparse(url).path or "/"
        return robots.is_allowed(path, self.user_agent)
    
    async def get_crawl_delay(self, url: str) -> Optional[float]:
        """Get crawl delay for URL."""
        robots = await self.fetch_robots(url)
        return robots.get_crawl_delay(self.user_agent)
    
    async def get_sitemaps(self, url: str) -> List[str]:
        """Get sitemap URLs from robots.txt."""
        robots = await self.fetch_robots(url)
        return robots.sitemaps
    
    def clear_cache(self) -> None:
        """Clear robots.txt cache."""
        self._cache.clear()


_robots_manager: Optional[RobotsManager] = None


def get_robots_manager(
    user_agent: str = "WebPort/1.0",
    respect_robots: bool = True,
) -> RobotsManager:
    """Get global robots manager."""
    global _robots_manager
    if _robots_manager is None:
        _robots_manager = RobotsManager(user_agent, respect_robots)
    return _robots_manager


__all__ = [
    "RobotsRule",
    "RobotsDirectives",
    "RobotsData",
    "RobotsParser",
    "RobotsManager",
    "get_robots_manager",
]
