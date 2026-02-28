"""
WebPort Base Migrator

Abstract base class for framework migrators.
"""

from __future__ import annotations

import logging
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from webport.core.config import MigrationConfig, WebPortConfig
from webport.core.models import CrawlResult, MigrationResult, WordPressPost

logger = logging.getLogger(__name__)


@dataclass
class MigrationContext:
    """Context for migration operation."""
    
    config: MigrationConfig
    crawl_result: CrawlResult
    output_dir: Path
    template_env: Environment
    
    # State
    files_created: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # Mappings
    url_mappings: Dict[str, str] = field(default_factory=dict)
    asset_mappings: Dict[str, str] = field(default_factory=dict)


class BaseMigrator(ABC):
    """
    Abstract base class for framework migrators.
    
    Subclasses implement:
    - _setup_project(): Create project structure
    - _generate_pages(): Generate page components
    - _generate_components(): Generate shared components
    - _copy_assets(): Copy and process assets
    """
    
    def __init__(
        self,
        crawl_result: CrawlResult,
        output_dir: Path,
        config: Optional[MigrationConfig] = None,
    ):
        self.crawl_result = crawl_result
        self.output_dir = Path(output_dir)
        self.config = config or MigrationConfig()
        
        # Setup Jinja2 template environment
        template_dir = self._get_template_dir()
        self.template_env = Environment(
            loader=FileSystemLoader(template_dir),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        
        self.context = MigrationContext(
            config=self.config,
            crawl_result=crawl_result,
            output_dir=self.output_dir,
            template_env=self.template_env,
        )
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Framework name."""
        pass
    
    @abstractmethod
    def _get_template_dir(self) -> Path:
        """Get path to framework templates."""
        pass
    
    @abstractmethod
    async def _setup_project(self) -> None:
        """Create project structure and configuration."""
        pass
    
    @abstractmethod
    async def _generate_pages(self) -> None:
        """Generate page components from crawled content."""
        pass
    
    @abstractmethod
    async def _generate_components(self) -> None:
        """Generate shared components."""
        pass
    
    @abstractmethod
    async def _copy_assets(self) -> None:
        """Copy and process static assets."""
        pass
    
    async def migrate(self) -> MigrationResult:
        """
        Execute the migration.
        
        Returns:
            MigrationResult with statistics and file list
        """
        start_time = datetime.utcnow()
        
        logger.info(f"Starting {self.name} migration to {self.output_dir}")
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Run migration steps
            await self._setup_project()
            await self._generate_pages()
            await self._generate_components()
            await self._copy_assets()
            
            # Create result
            result = MigrationResult(
                source_url=self.crawl_result.target_url,
                target_framework=self.name,
                output_path=str(self.output_dir),
                started_at=start_time,
                completed_at=datetime.utcnow(),
                pages_generated=len(self.context.files_created),
                files_created=self.context.files_created,
                warnings=self.context.warnings,
                success=True,
            )
            
            result.duration_seconds = (
                result.completed_at - result.started_at
            ).total_seconds()
            
            logger.info(
                f"Migration complete: {result.pages_generated} files created "
                f"in {result.duration_seconds:.1f}s"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return MigrationResult(
                source_url=self.crawl_result.target_url,
                target_framework=self.name,
                output_path=str(self.output_dir),
                started_at=start_time,
                completed_at=datetime.utcnow(),
                success=False,
                warnings=[str(e)],
            )
    
    def _write_file(self, path: Path, content: str) -> None:
        """Write content to file and track it."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        
        rel_path = str(path.relative_to(self.output_dir))
        self.context.files_created.append(rel_path)
        logger.debug(f"Created: {rel_path}")
    
    def _render_template(self, template_name: str, **kwargs) -> str:
        """Render a Jinja2 template."""
        template = self.template_env.get_template(template_name)
        return template.render(**kwargs)
    
    def _slugify(self, text: str) -> str:
        """Convert text to URL-safe slug."""
        import re
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[-\s]+", "-", text)
        return text
    
    def _html_to_markdown(self, html: str) -> str:
        """Convert HTML to Markdown."""
        # Simple conversion - in production, use markdownify or similar
        import re
        
        # Remove scripts and styles
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
        
        # Convert common elements
        html = re.sub(r"<h1[^>]*>(.*?)</h1>", r"# \1\n", html, flags=re.DOTALL)
        html = re.sub(r"<h2[^>]*>(.*?)</h2>", r"## \1\n", html, flags=re.DOTALL)
        html = re.sub(r"<h3[^>]*>(.*?)</h3>", r"### \1\n", html, flags=re.DOTALL)
        html = re.sub(r"<p[^>]*>(.*?)</p>", r"\1\n\n", html, flags=re.DOTALL)
        html = re.sub(r"<br\s*/?>", "\n", html)
        html = re.sub(r"<strong[^>]*>(.*?)</strong>", r"**\1**", html, flags=re.DOTALL)
        html = re.sub(r"<em[^>]*>(.*?)</em>", r"*\1*", html, flags=re.DOTALL)
        html = re.sub(r"<a[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", r"[\2](\1)", html, flags=re.DOTALL)
        
        # Remove remaining tags
        html = re.sub(r"<[^>]+>", "", html)
        
        # Clean up whitespace
        html = re.sub(r"\n{3,}", "\n\n", html)
        
        return html.strip()


__all__ = ["BaseMigrator", "MigrationContext"]
