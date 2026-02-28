"""Detail scraper — extracts supplemental fields from individual pages."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Union

from webport.core.config import DetailScrapeConfig, SiteConfig
from webport.core.models import ScrapeResult
from webport.scrapers.base import BaseScraper, SelectorEngine

logger = logging.getLogger(__name__)


class DetailScraper(BaseScraper):
    """Scrape supplemental fields from individual item pages.

    Given a source JSON (e.g., wp_participants.json), visits each item's page
    and extracts configured fields using CSS selectors.
    """

    def __init__(
        self,
        site_config: SiteConfig,
        config: DetailScrapeConfig,
        **kwargs: Any,
    ) -> None:
        super().__init__(site_config, **kwargs)
        self.config = config

    async def scrape(self) -> ScrapeResult:
        """Scrape detail fields from all source items."""
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
                extracted: Dict[str, Any] = {"slug": slug, "url": url}

                for field_name, selector_config in self.config.fields.items():
                    value = engine.select(selector_config)
                    extracted[field_name] = value

                results[slug] = extracted
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
