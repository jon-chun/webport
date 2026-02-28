"""
WebPort CLI

Command-line interface for WebPort — reverse-engineer any website, port it anywhere.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Optional, Set
from urllib.parse import urlparse

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm
from rich.table import Table

from webport import __version__

app = typer.Typer(
    name="webport",
    help="Reverse-engineer any website. Port it anywhere.",
    add_completion=True,
    no_args_is_help=True,
)

console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        console.print(f"[bold cyan]WebPort[/bold cyan] v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show version and exit",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-V", help="Enable verbose output",
    ),
) -> None:
    """WebPort - Reverse-engineer any website. Port it anywhere."""
    pass


def _domain_from_url(url: str) -> str:
    """Extract domain from URL, stripping www. prefix."""
    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _load_site_config(
    url: Optional[str] = None,
    site_dir: Optional[Path] = None,
    config_path: Optional[Path] = None,
) -> "SiteConfig":
    """Load or create a SiteConfig."""
    from webport.core.config import SiteConfig

    if config_path and config_path.exists():
        return SiteConfig.from_yaml(config_path)

    if site_dir:
        domain = site_dir.name
        yaml_path = site_dir / "webport.yaml"
        if yaml_path.exists():
            return SiteConfig.from_yaml(yaml_path)
        return SiteConfig(domain=domain, base_url=f"https://{domain}")

    if url:
        domain = _domain_from_url(url)
        yaml_path = Path("sites") / domain / "webport.yaml"
        if yaml_path.exists():
            return SiteConfig.from_yaml(yaml_path)
        return SiteConfig(domain=domain, base_url=url.rstrip("/"))

    raise typer.BadParameter("Must provide URL or site directory")


# =============================================================================
# crawl command
# =============================================================================

@app.command()
def crawl(
    url: str = typer.Argument(..., help="URL to crawl"),
    wordpress: bool = typer.Option(
        True, "--wordpress/--no-wordpress", "-w", help="Use WordPress API",
    ),
    resume: bool = typer.Option(
        False, "--resume", help="Resume interrupted crawl",
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to webport.yaml",
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompts",
    ),
) -> None:
    """Crawl a website and extract content via WordPress REST API."""
    site_config = _load_site_config(url=url, config_path=config)

    console.print(Panel.fit(
        f"[bold cyan]WebPort Crawl[/bold cyan]\n"
        f"Target: {url}\n"
        f"Domain: {site_config.domain}\n"
        f"Mode: {'WordPress API' if wordpress else 'Static HTML'}",
        title="Crawl",
    ))

    if not yes:
        if not Confirm.ask(f"Start crawling {url}?"):
            console.print("[yellow]Crawl cancelled[/yellow]")
            raise typer.Exit(0)

    site_config.input_dir.mkdir(parents=True, exist_ok=True)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Crawling...", total=None)

        try:
            from webport.core.config import WebPortConfig
            from webport.crawlers import WordPressCrawler, StaticSiteCrawler

            wp_config = WebPortConfig(
                target_url=url,
                output_dir=site_config.input_dir,
            )

            if wordpress:
                crawler = WordPressCrawler(wp_config)
            else:
                crawler = StaticSiteCrawler(wp_config)

            pages = asyncio.run(crawler.crawl())
            progress.update(task, description=f"Crawled {len(pages)} pages")
        except KeyboardInterrupt:
            console.print("\n[yellow]Crawl interrupted. Progress saved.[/yellow]")
            raise typer.Exit(130)

    console.print(f"[green]OK[/green] Crawl complete — data saved to {site_config.input_dir}")


# =============================================================================
# scrape command
# =============================================================================

@app.command()
def scrape(
    url: str = typer.Argument(..., help="URL of the site to scrape"),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to webport.yaml",
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompts",
    ),
) -> None:
    """Scrape supplemental data from HTML pages (relationships, details)."""
    site_config = _load_site_config(url=url, config_path=config)

    if not site_config.input_dir.exists():
        console.print(f"[red]Error:[/red] No crawl data at {site_config.input_dir}")
        console.print("Run 'webport crawl' first.")
        raise typer.Exit(1)

    rel_count = len(site_config.scrape.relationships)
    det_count = len(site_config.scrape.details)

    if rel_count == 0 and det_count == 0:
        console.print("[yellow]No scrape configs defined in webport.yaml[/yellow]")
        raise typer.Exit(0)

    console.print(Panel.fit(
        f"[bold cyan]WebPort Scrape[/bold cyan]\n"
        f"Domain: {site_config.domain}\n"
        f"Relationships: {rel_count} | Details: {det_count}",
        title="Scrape",
    ))

    if not yes:
        if not Confirm.ask("Start scraping?"):
            raise typer.Exit(0)

    from webport.scrapers.relationship import RelationshipScraper
    from webport.scrapers.detail import DetailScraper

    async def run_scrapers() -> None:
        import httpx
        async with httpx.AsyncClient(
            timeout=site_config.scrape.timeout,
            follow_redirects=True,
            headers={"User-Agent": "WebPort/1.0"},
        ) as client:
            for rel_config in site_config.scrape.relationships:
                s = RelationshipScraper(site_config, rel_config, client=client)
                result = await s.scrape()
                status = "[green]OK[/green]" if not result.errors else "[yellow]WARN[/yellow]"
                console.print(
                    f"  {status} {rel_config.output_file}: "
                    f"{result.items_scraped}/{result.items_processed} items"
                )

            for det_config in site_config.scrape.details:
                s = DetailScraper(site_config, det_config, client=client)
                result = await s.scrape()
                status = "[green]OK[/green]" if not result.errors else "[yellow]WARN[/yellow]"
                console.print(
                    f"  {status} {det_config.output_file}: "
                    f"{result.items_scraped}/{result.items_processed} items"
                )

    asyncio.run(run_scrapers())
    console.print(f"\n[green]OK[/green] Scraping complete")


# =============================================================================
# analyze command
# =============================================================================

@app.command()
def analyze(
    site_dir: Path = typer.Argument(..., help="Path to site directory (e.g., sites/example.com)"),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to webport.yaml",
    ),
) -> None:
    """Analyze crawled site data and generate documentation."""
    site_config = _load_site_config(site_dir=site_dir, config_path=config)

    if not site_config.input_dir.exists():
        console.print(f"[red]Error:[/red] No crawl data at {site_config.input_dir}")
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"[bold cyan]WebPort Analyze[/bold cyan]\n"
        f"Site: {site_config.domain}\n"
        f"Docs: {', '.join(site_config.analyze.docs)}",
        title="Analyze",
    ))

    from webport.analyzers.doc_generator import generate_docs

    result = generate_docs(site_config)

    if result.success:
        console.print(
            f"[green]OK[/green] Generated {result.file_count} docs to {site_config.docs_dir}"
        )
    else:
        console.print(f"[red]FAIL[/red] {', '.join(result.errors)}")
        raise typer.Exit(1)


# =============================================================================
# generate command
# =============================================================================

@app.command()
def generate(
    site_dir: Path = typer.Argument(..., help="Path to site directory"),
    target: str = typer.Option(
        "nextjs", "--target", "-t", help="Target framework (nextjs)",
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to webport.yaml",
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompts",
    ),
) -> None:
    """Generate framework code from crawled data."""
    site_config = _load_site_config(site_dir=site_dir, config_path=config)

    if not site_config.input_dir.exists():
        console.print(f"[red]Error:[/red] No crawl data at {site_config.input_dir}")
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"[bold cyan]WebPort Generate[/bold cyan]\n"
        f"Site: {site_config.domain}\n"
        f"Target: {target}",
        title="Generate",
    ))

    if not yes:
        if not Confirm.ask(f"Generate {target} project?"):
            raise typer.Exit(0)

    from webport.generators.base import run_generator

    result = run_generator(site_config)

    if result.success:
        console.print(
            f"[green]OK[/green] Generated {result.file_count} files to "
            f"{site_config.output_dir / target}"
        )
    else:
        console.print(f"[red]FAIL[/red] {', '.join(result.errors)}")
        raise typer.Exit(1)


# =============================================================================
# archive command
# =============================================================================

@app.command()
def archive(
    site_dir: Path = typer.Argument(..., help="Path to site directory"),
) -> None:
    """Create a ZIP archive of all site data."""
    site_config = _load_site_config(site_dir=site_dir)

    if not site_config.sites_dir.exists():
        console.print(f"[red]Error:[/red] Site directory not found: {site_config.sites_dir}")
        raise typer.Exit(1)

    from webport.pipeline.archive import create_archive

    console.print(f"[bold cyan]Archiving[/bold cyan] {site_config.domain}...")
    result = create_archive(site_config)

    if result.success:
        archive_path = result.metadata.get("archive_path", "")
        size_mb = result.metadata.get("size_bytes", 0) / (1024 * 1024)
        console.print(
            f"[green]OK[/green] Created {archive_path} "
            f"({result.file_count} files, {size_mb:.1f} MB)"
        )
    else:
        console.print(f"[red]FAIL[/red] {', '.join(result.errors)}")
        raise typer.Exit(1)


# =============================================================================
# pipeline command
# =============================================================================

@app.command()
def pipeline(
    url: str = typer.Argument(..., help="URL to process"),
    stages: Optional[str] = typer.Option(
        None, "--stages", "-s",
        help="Comma-separated stages (crawl,scrape,analyze,generate,archive)",
    ),
    skip: Optional[str] = typer.Option(
        None, "--skip", help="Comma-separated stages to skip",
    ),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to webport.yaml",
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation prompts",
    ),
) -> None:
    """Run the full crawl -> scrape -> analyze -> generate -> archive pipeline."""
    from webport.core.config import SiteConfig
    from webport.core.models import StageResult
    from webport.pipeline.stages import Stage
    from webport.pipeline.orchestrator import PipelineOrchestrator
    from webport.pipeline.archive import create_archive

    site_config = _load_site_config(url=url, config_path=config)

    if stages:
        stage_list = Stage.parse_stages(stages)
    else:
        stage_list = Stage.all_stages()

    skip_set: Set[Stage] = set()
    if skip:
        skip_set = {Stage(s.strip()) for s in skip.split(",")}

    if not yes:
        stage_names = ", ".join(s.value for s in stage_list if s not in skip_set)
        if not Confirm.ask(f"Run pipeline ({stage_names}) for {url}?"):
            raise typer.Exit(0)

    orchestrator = PipelineOrchestrator(site_config, console)

    # Register stage runners
    def run_crawl(sc: SiteConfig) -> StageResult:
        sc.input_dir.mkdir(parents=True, exist_ok=True)
        from webport.core.config import WebPortConfig
        from webport.crawlers import WordPressCrawler
        wp_config = WebPortConfig(target_url=sc.base_url, output_dir=sc.input_dir)
        crawler = WordPressCrawler(wp_config)
        pages = asyncio.run(crawler.crawl())
        files = list(sc.input_dir.glob("*.json"))
        return StageResult(
            stage="crawl", success=True,
            file_count=len(files),
            files_created=[str(f) for f in files],
        )

    def run_scrape(sc: SiteConfig) -> StageResult:
        from webport.scrapers.relationship import RelationshipScraper
        from webport.scrapers.detail import DetailScraper
        import httpx

        total_scraped = 0
        errors: list[str] = []

        async def _run() -> None:
            nonlocal total_scraped
            async with httpx.AsyncClient(
                timeout=sc.scrape.timeout, follow_redirects=True,
            ) as client:
                for rel in sc.scrape.relationships:
                    s = RelationshipScraper(sc, rel, client=client)
                    r = await s.scrape()
                    total_scraped += r.items_scraped
                    errors.extend(r.errors)
                for det in sc.scrape.details:
                    s = DetailScraper(sc, det, client=client)
                    r = await s.scrape()
                    total_scraped += r.items_scraped
                    errors.extend(r.errors)

        asyncio.run(_run())
        files = list(sc.input_dir.glob("*.json"))
        return StageResult(
            stage="scrape", success=len(errors) == 0,
            file_count=len(files), errors=errors[:5],
        )

    def run_analyze(sc: SiteConfig) -> StageResult:
        from webport.analyzers.doc_generator import generate_docs
        return generate_docs(sc)

    def run_generate(sc: SiteConfig) -> StageResult:
        from webport.generators.base import run_generator
        return run_generator(sc)

    def run_archive(sc: SiteConfig) -> StageResult:
        return create_archive(sc)

    orchestrator.register(Stage.CRAWL, run_crawl)
    orchestrator.register(Stage.SCRAPE, run_scrape)
    orchestrator.register(Stage.ANALYZE, run_analyze)
    orchestrator.register(Stage.GENERATE, run_generate)
    orchestrator.register(Stage.ARCHIVE, run_archive)

    results = orchestrator.run(stage_list, skip_set)

    if any(not r.success for r in results.values()):
        raise typer.Exit(1)


# =============================================================================
# check command
# =============================================================================

@app.command()
def check(
    url: str = typer.Argument(..., help="URL to check"),
) -> None:
    """Run health checks on a URL."""
    from webport.crawlers.utils.health import check_site_health

    console.print(f"[bold cyan]Checking[/bold cyan] {url}")

    with console.status("[bold green]Running health checks..."):
        health = asyncio.run(check_site_health(url))

    console.print(health.report())

    if health.is_healthy:
        console.print("\n[bold green]Site is healthy and ready to crawl[/bold green]")
    elif health.can_crawl:
        console.print("\n[bold yellow]Site has some issues but can be crawled[/bold yellow]")
    else:
        console.print("\n[bold red]Site cannot be crawled[/bold red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
