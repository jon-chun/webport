"""Base analyzer abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from webport.core.config import SiteConfig
from webport.core.models import StageResult


class BaseAnalyzer(ABC):
    """Base class for site analyzers."""

    def __init__(self, site_config: SiteConfig) -> None:
        self.site_config = site_config

    @abstractmethod
    def analyze(self) -> StageResult:
        """Run analysis and return result."""
        ...

    def load_json(self, filename: str) -> Any:
        """Load a JSON file from the input directory."""
        import json
        path = self.site_config.input_dir / filename
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)
