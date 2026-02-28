# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

WebPort is a production-grade website reverse engineering and porting toolkit. It crawls websites (especially WordPress), extracts content/structure, and generates modern framework code (Next.js). Tagline: "Reverse-engineer any website. Port it anywhere."

## Commands

### Development Setup
```bash
pip install -e ".[dev]"
playwright install chromium
pre-commit install
```

### Testing
```bash
pytest                                    # All tests
pytest tests/test_core.py                 # Single file
pytest tests/unit/core/ -v                # Specific module
pytest -m unit                            # Unit tests only
pytest -m integration                     # Integration tests
pytest -m contract                        # Contract tests (API validation)
pytest tests/test_properties.py -v        # Property-based tests (Hypothesis)
pytest --cov=webport --cov-report=html    # With coverage
pytest -n auto                            # Parallel execution
```

### Linting & Type Checking
```bash
ruff check src tests                # Linting
ruff check src tests --fix          # Auto-fix
black src tests                     # Formatting
mypy src                            # Type checking
```

### CLI
```bash
webport --version
webport check https://example.com                          # Health check
webport crawl https://example.com                          # Crawl site
webport scrape https://example.com                         # Scrape supplemental data
webport analyze sites/example.com                          # Analyze crawled data
webport generate sites/example.com --target nextjs         # Generate code
webport archive sites/example.com                          # Create ZIP archive
webport pipeline https://example.com                       # Full pipeline
webport pipeline https://example.com --stages crawl,scrape # Partial pipeline
```

## Architecture

### Multi-Stage Pipeline
```
URL -> [1.crawl] -> [2.scrape] -> [3.analyze] -> [4.generate] -> [5.archive] -> ZIP
```

Each stage is independently runnable. The pipeline orchestrator handles sequencing and dependency validation.

### Async-First Design (ADR-001)
All I/O operations use `asyncio` with `httpx` for HTTP. Sync wrappers exist for CLI via `asyncio.run()`. Use `run_in_executor()` for blocking operations.

### Data Models (ADR-002)
All data structures use Pydantic v2. Configuration uses `pydantic-settings`. Field validators handle complex validation.

### Checkpoint System (ADR-003)
File-based checkpoints enable resume after interruption. Uses atomic writes (temp file + rename) and SHA-256 content hashing for change detection.

### Code Structure
```
src/webport/
├── forge.py              # Main WebPort class - orchestrates pipeline
├── cli/main.py           # Typer CLI entry point
├── core/
│   ├── config.py         # WebPortConfig + SiteConfig (Pydantic settings)
│   ├── models.py         # CrawledPage, CrawlResult, ScrapeResult, etc.
│   ├── checkpoint.py     # Resume capability
│   ├── container.py      # Dependency injection container
│   ├── plugins.py        # Plugin system with hooks
│   ├── rate_limiter.py   # Token bucket algorithm
│   ├── retry.py          # Retry with circuit breaker
│   ├── security.py       # SSRF protection, PII detection
│   └── shutdown.py       # Graceful shutdown handler
├── crawlers/
│   ├── base.py           # BaseCrawler abstract class
│   ├── wordpress.py      # WordPress REST API crawler
│   └── static.py         # HTTP-based static site crawler
├── scrapers/             # Config-driven HTML scrapers
│   ├── base.py           # SelectorEngine + BaseScraper
│   ├── relationship.py   # M2M relationship extraction
│   └── detail.py         # Supplemental field extraction
├── analyzers/            # Documentation generators
│   ├── base.py           # BaseAnalyzer ABC
│   └── doc_generator.py  # Template-based doc generation
├── generators/           # Code generators
│   ├── base.py           # BaseGenerator
│   └── nextjs/           # Next.js project generation
├── pipeline/             # Pipeline orchestration
│   ├── orchestrator.py   # Stage sequencing + dependency validation
│   ├── stages.py         # Stage enum, StageResult
│   └── archive.py        # ZIP packaging
└── migrators/
    ├── base.py           # BaseMigrator abstract class
    └── nextjs/           # Next.js code generator
```

### Key Patterns
- **Crawlers** inherit from `BaseCrawler` and implement `crawl() -> List[CrawledPage]`
- **Scrapers** are config-driven via CSS selectors in `webport.yaml`
- **Migrators** inherit from `BaseMigrator` and implement `migrate() -> MigrationResult`
- **Plugins** inherit from `BasePlugin` with hooks: `pre_crawl`, `post_crawl`, `on_page_crawled`, `pre_extract`, `post_extract`, `pre_migrate`, `post_migrate`
- **WebPort.run()** orchestrates the pipeline: health check -> detect site type -> crawl -> analyze -> migrate

### Configuration Hierarchy
Configuration sources applied in order (later overrides earlier):
1. Default values in code
2. Site config file (`sites/{domain}/webport.yaml`)
3. Environment variables (`WEBPORT_` prefix, `__` for nesting: `WEBPORT_CRAWLER__MAX_PAGES`)
4. CLI arguments

### Security
- **SSRF Protection**: Blocks internal IP ranges (10.x, 172.16.x, 192.168.x, 127.x, 169.254.x) by default
- **PII Detection**: `ContentAnonymizer` detects emails, phones, SSNs, credit cards
- **Credential Encryption**: `EncryptedStr` for sensitive config values

## Code Style

- Line length: 100 characters
- Type hints required on all functions
- Ruff handles linting and imports (isort-compatible)
- Black handles formatting
- MyPy strict mode enabled
- Follows [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, etc.
