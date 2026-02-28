"""Pipeline stage definitions."""

from __future__ import annotations

from enum import Enum
from typing import Dict, List, Set


class Stage(str, Enum):
    """Pipeline stages in execution order."""

    CRAWL = "crawl"
    SCRAPE = "scrape"
    ANALYZE = "analyze"
    GENERATE = "generate"
    ARCHIVE = "archive"

    @classmethod
    def all_stages(cls) -> List["Stage"]:
        """Return all stages in execution order."""
        return [cls.CRAWL, cls.SCRAPE, cls.ANALYZE, cls.GENERATE, cls.ARCHIVE]

    @classmethod
    def dependencies(cls) -> Dict["Stage", Set["Stage"]]:
        """Return stage dependency map (stage -> required prior stages)."""
        return {
            cls.CRAWL: set(),
            cls.SCRAPE: {cls.CRAWL},
            cls.ANALYZE: {cls.CRAWL},
            cls.GENERATE: {cls.CRAWL},
            cls.ARCHIVE: set(),  # Can archive whatever exists
        }

    @classmethod
    def parse_stages(cls, stages_str: str) -> List["Stage"]:
        """Parse comma-separated stage names into ordered list."""
        requested = [cls(s.strip()) for s in stages_str.split(",")]
        all_ordered = cls.all_stages()
        return [s for s in all_ordered if s in requested]

    def requires(self) -> Set["Stage"]:
        """Get stages that must run before this one."""
        return self.dependencies().get(self, set())
