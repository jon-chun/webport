"""Base generator and runner for code generation."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List

from webport.core.config import SiteConfig
from webport.core.models import StageResult

logger = logging.getLogger(__name__)


class BaseGenerator(ABC):
    """Base class for code generators."""

    def __init__(self, site_config: SiteConfig) -> None:
        self.site_config = site_config

    @abstractmethod
    def generate(self) -> StageResult:
        """Generate framework code and return result."""
        ...

    def load_json(self, filename: str) -> Any:
        """Load a JSON file from the input directory."""
        path = self.site_config.input_dir / filename
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)


def run_generator(site_config: SiteConfig) -> StageResult:
    """Run the appropriate generator based on site config."""
    target = site_config.generate.target.value

    if target == "nextjs":
        from webport.generators.nextjs.generator import NextJSGenerator
        gen = NextJSGenerator(site_config)
        return gen.generate()
    else:
        return StageResult(
            stage="generate",
            success=False,
            errors=[f"Unsupported target: {target}"],
        )
