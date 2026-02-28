"""WebPort scrapers — config-driven HTML scraping engine."""

from webport.scrapers.base import SelectorEngine, BaseScraper
from webport.scrapers.relationship import RelationshipScraper
from webport.scrapers.detail import DetailScraper

__all__ = ["SelectorEngine", "BaseScraper", "RelationshipScraper", "DetailScraper"]
