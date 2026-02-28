"""Pipeline orchestrator — sequences stages with dependency validation."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set
from urllib.parse import urlparse

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from webport.core.config import SiteConfig
from webport.core.models import StageResult
from webport.pipeline.stages import Stage

logger = logging.getLogger(__name__)

# Type alias for stage runner functions
StageRunner = Callable[[SiteConfig], StageResult]


class PipelineOrchestrator:
    """Orchestrates multi-stage pipeline execution."""

    def __init__(
        self,
        site_config: SiteConfig,
        console: Optional[Console] = None,
    ) -> None:
        self.site_config = site_config
        self.console = console or Console()
        self.results: Dict[Stage, StageResult] = {}
        self._runners: Dict[Stage, StageRunner] = {}

    def register(self, stage: Stage, runner: StageRunner) -> None:
        """Register a runner function for a stage."""
        self._runners[stage] = runner

    def validate_stages(
        self,
        stages: List[Stage],
        skip: Optional[Set[Stage]] = None,
    ) -> List[Stage]:
        """Validate and filter stages, checking dependencies.

        Returns the ordered list of stages to execute.
        Raises ValueError if dependencies are not met.
        """
        skip = skip or set()
        to_run = [s for s in stages if s not in skip]

        # Check dependencies
        deps = Stage.dependencies()
        for stage in to_run:
            required = deps.get(stage, set())
            for req in required:
                if req not in to_run and not self._stage_data_exists(req):
                    raise ValueError(
                        f"Stage '{stage.value}' requires '{req.value}' but it is not "
                        f"scheduled and no prior data exists."
                    )

        return to_run

    def _stage_data_exists(self, stage: Stage) -> bool:
        """Check if output data exists from a prior run of this stage."""
        input_dir = self.site_config.input_dir
        output_dir = self.site_config.output_dir

        if stage == Stage.CRAWL:
            return input_dir.exists() and any(input_dir.glob("wp_*.json"))
        elif stage == Stage.SCRAPE:
            return input_dir.exists() and any(
                f.exists()
                for f in [
                    input_dir / "roundtable_participants.json",
                    input_dir / "participant_titles.json",
                ]
            )
        elif stage == Stage.ANALYZE:
            docs_dir = output_dir / "docs"
            return docs_dir.exists() and any(docs_dir.glob("*.md"))
        elif stage == Stage.GENERATE:
            return (output_dir / "nextjs").exists()
        elif stage == Stage.ARCHIVE:
            return True  # Can always archive
        return False

    def run(
        self,
        stages: Optional[List[Stage]] = None,
        skip: Optional[Set[Stage]] = None,
    ) -> Dict[Stage, StageResult]:
        """Run the pipeline stages in order."""
        stages = stages or Stage.all_stages()
        to_run = self.validate_stages(stages, skip)

        self.console.print(
            Panel.fit(
                f"[bold cyan]WebPort Pipeline[/bold cyan]\n"
                f"Site: {self.site_config.domain}\n"
                f"Stages: {', '.join(s.value for s in to_run)}",
                title="Pipeline",
            )
        )

        for stage in to_run:
            runner = self._runners.get(stage)
            if not runner:
                self.console.print(
                    f"  [yellow]SKIP[/yellow] {stage.value} — no runner registered"
                )
                continue

            self.console.print(f"\n  [bold cyan]>>>[/bold cyan] {stage.value}")
            start = time.time()

            try:
                result = runner(self.site_config)
                result.duration_seconds = time.time() - start
                self.results[stage] = result

                if result.success:
                    self.console.print(
                        f"  [green]OK[/green] {stage.value} "
                        f"({result.duration_seconds:.1f}s, "
                        f"{result.file_count} files)"
                    )
                else:
                    self.console.print(
                        f"  [red]FAIL[/red] {stage.value}: "
                        f"{', '.join(result.errors[:3])}"
                    )
            except Exception as e:
                elapsed = time.time() - start
                result = StageResult(
                    stage=stage.value,
                    success=False,
                    duration_seconds=elapsed,
                    errors=[str(e)],
                )
                self.results[stage] = result
                self.console.print(f"  [red]ERROR[/red] {stage.value}: {e}")
                logger.exception(f"Stage {stage.value} failed")

        self._print_summary()
        return self.results

    def _print_summary(self) -> None:
        """Print pipeline execution summary."""
        table = Table(title="\nPipeline Summary")
        table.add_column("Stage", style="cyan")
        table.add_column("Status")
        table.add_column("Duration", justify="right")
        table.add_column("Files", justify="right")

        for stage, result in self.results.items():
            status = "[green]OK[/green]" if result.success else "[red]FAIL[/red]"
            table.add_row(
                stage.value,
                status,
                f"{result.duration_seconds:.1f}s",
                str(result.file_count),
            )

        self.console.print(table)


def domain_from_url(url: str) -> str:
    """Extract domain from URL."""
    parsed = urlparse(url)
    return parsed.netloc or parsed.path
