"""Config-driven scraper with CSS selector engine."""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from webport.core.config import SelectorConfig, SiteConfig
from webport.core.models import ScrapeResult

logger = logging.getLogger(__name__)


class SelectorEngine:
    """Evaluate CSS selectors with fallback chains against a BeautifulSoup document."""

    def __init__(self, soup: BeautifulSoup) -> None:
        self.soup = soup

    def select(self, config: SelectorConfig) -> Union[str, List[str], None]:
        """Evaluate a SelectorConfig against the document.

        Tries each selector in order. Returns the first successful match.
        """
        for selector in config.selectors:
            try:
                if config.multiple:
                    elements = self.soup.select(selector)
                    if elements:
                        values = [self._extract_value(el, config) for el in elements]
                        values = [v for v in values if v]
                        if values:
                            return values
                else:
                    element = self.soup.select_one(selector)
                    if element:
                        value = self._extract_value(element, config)
                        if value:
                            return value
            except Exception as e:
                logger.debug(f"Selector '{selector}' failed: {e}")
                continue

        return [] if config.multiple else None

    def _extract_value(self, element: Tag, config: SelectorConfig) -> Optional[str]:
        """Extract value from an element based on config."""
        if config.attribute:
            raw = element.get(config.attribute)
            if isinstance(raw, list):
                raw = raw[0] if raw else None
        else:
            raw = element.get_text(strip=True)

        if raw is None:
            return None

        value = str(raw).strip()
        return self._transform(value, config.transform)

    def _transform(self, value: str, transform: Optional[str]) -> str:
        """Apply post-processing transform."""
        if not transform:
            return value

        if transform == "strip":
            return value.strip()
        elif transform == "slug":
            return value.lower().replace(" ", "-")
        elif transform == "url":
            return value  # URL normalization handled by caller
        elif transform == "date":
            return value  # Date parsing handled by caller
        return value


class BaseScraper(ABC):
    """Base class for config-driven scrapers."""

    def __init__(
        self,
        site_config: SiteConfig,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.site_config = site_config
        self._client = client
        self._owns_client = client is None
        self.base_url = site_config.base_url

    async def __aenter__(self) -> "BaseScraper":
        if self._owns_client:
            self._client = httpx.AsyncClient(
                timeout=self.site_config.scrape.timeout,
                follow_redirects=True,
                headers={"User-Agent": "WebPort/1.0"},
            )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._owns_client and self._client:
            await self._client.aclose()

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("Scraper not initialized — use 'async with' context manager")
        return self._client

    async def fetch_html(self, url: str) -> Optional[BeautifulSoup]:
        """Fetch a URL and return parsed HTML."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return None

    def load_source_json(self, filename: str) -> List[Dict[str, Any]]:
        """Load source JSON data from the input directory."""
        path = self.site_config.input_dir / filename
        if not path.exists():
            logger.error(f"Source file not found: {path}")
            return []
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []

    def save_json(self, filename: str, data: Any) -> Path:
        """Save JSON data to the input directory."""
        path = self.site_config.input_dir / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Saved {path} ({len(data) if isinstance(data, (list, dict)) else '?'} items)")
        return path

    @abstractmethod
    async def scrape(self) -> ScrapeResult:
        """Run the scraping operation. Subclasses must implement."""
        ...
