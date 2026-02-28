"""Relationship scraper — extracts M2M relationships from HTML pages."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from webport.core.config import RelationshipScrapeConfig, SiteConfig
from webport.core.models import ScrapeResult
from webport.scrapers.base import BaseScraper, SelectorEngine

logger = logging.getLogger(__name__)


class RelationshipScraper(BaseScraper):
    """Scrape M2M relationships by visiting pages and extracting linked items.

    Given a source JSON (e.g., wp_posts.json), visits each item's page URL
    and extracts related items (e.g., participants linked to a roundtable)
    using CSS selectors defined in the config.
    """

    def __init__(
        self,
        site_config: SiteConfig,
        config: RelationshipScrapeConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(site_config, **kwargs)
        self.config = config

    async def scrape(self) -> ScrapeResult:
        """Scrape relationships from all source items."""
        items = self.load_source_json(self.config.source_json)
        if not items:
            return ScrapeResult(
                source_file=self.config.source_json,
                output_file=self.config.output_file,
                errors=[f"No items in {self.config.source_json}"],
            )

        start = time.time()
        semaphore = asyncio.Semaphore(self.site_config.scrape.max_concurrent)
        results: Dict[str, Dict[str, Any]] = {}
        errors: List[str] = []
        failed = 0

        async def scrape_one(item: Dict[str, Any]) -> None:
            nonlocal failed
            async with semaphore:
                slug = item.get("slug", "")
                url = item.get(self.config.url_field, "")
                if not url:
                    return

                soup = await self.fetch_html(url)
                if not soup:
                    failed += 1
                    errors.append(f"Failed to fetch {url}")
                    return

                engine = SelectorEngine(soup)

                # Extract related item links
                links = engine.select(self.config.target_link)
                names = None
                if self.config.target_name:
                    names = engine.select(self.config.target_name)

                related: List[Dict[str, str]] = []
                if isinstance(links, list):
                    for i, link in enumerate(links):
                        entry: Dict[str, str] = {"link": link}
                        if isinstance(names, list) and i < len(names):
                            entry["name"] = names[i]
                        # Extract slug from link
                        parts = link.rstrip("/").split("/")
                        if parts:
                            entry["slug"] = parts[-1]
                        related.append(entry)

                results[slug] = {
                    "slug": slug,
                    "url": url,
                    "related_count": len(related),
                    "related": related,
                }

                await asyncio.sleep(self.site_config.scrape.rate_limit_delay)

        tasks = [scrape_one(item) for item in items]
        await asyncio.gather(*tasks)

        # Save results
        output_data = list(results.values())
        self.save_json(self.config.output_file, output_data)

        return ScrapeResult(
            source_file=self.config.source_json,
            output_file=self.config.output_file,
            items_processed=len(items),
            items_scraped=len(results),
            items_failed=failed,
            duration_seconds=time.time() - start,
            errors=errors[:10],
        )
