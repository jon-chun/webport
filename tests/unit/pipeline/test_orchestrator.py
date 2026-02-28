"""Tests for the pipeline orchestrator."""

import pytest
from unittest.mock import MagicMock

from webport.core.config import SiteConfig
from webport.core.models import StageResult
from webport.pipeline.stages import Stage
from webport.pipeline.orchestrator import PipelineOrchestrator, domain_from_url


@pytest.fixture
def site_config():
    return SiteConfig(
        domain="example.com",
        base_url="https://example.com",
    )


@pytest.fixture
def orchestrator(site_config):
    console = MagicMock()
    return PipelineOrchestrator(site_config, console)


class TestStage:
    """Test Stage enum functionality."""

    def test_all_stages_order(self):
        stages = Stage.all_stages()
        assert stages == [
            Stage.CRAWL, Stage.SCRAPE, Stage.ANALYZE, Stage.GENERATE, Stage.ARCHIVE,
        ]

    def test_parse_stages(self):
        result = Stage.parse_stages("crawl,scrape")
        assert result == [Stage.CRAWL, Stage.SCRAPE]

    def test_parse_stages_reorders(self):
        result = Stage.parse_stages("scrape,crawl")
        assert result == [Stage.CRAWL, Stage.SCRAPE]

    def test_parse_single_stage(self):
        result = Stage.parse_stages("archive")
        assert result == [Stage.ARCHIVE]

    def test_dependencies(self):
        deps = Stage.dependencies()
        assert deps[Stage.CRAWL] == set()
        assert Stage.CRAWL in deps[Stage.SCRAPE]
        assert Stage.CRAWL in deps[Stage.ANALYZE]
        assert deps[Stage.ARCHIVE] == set()

    def test_requires(self):
        assert Stage.CRAWL.requires() == set()
        assert Stage.SCRAPE.requires() == {Stage.CRAWL}


class TestPipelineOrchestrator:
    """Test pipeline orchestration logic."""

    def test_validate_stages_no_deps(self, orchestrator):
        result = orchestrator.validate_stages([Stage.ARCHIVE])
        assert result == [Stage.ARCHIVE]

    def test_validate_stages_with_skip(self, orchestrator):
        result = orchestrator.validate_stages(
            Stage.all_stages(),
            skip={Stage.ARCHIVE},
        )
        assert Stage.ARCHIVE not in result
        assert Stage.CRAWL in result

    def test_validate_stages_dep_failure(self, orchestrator):
        with pytest.raises(ValueError, match="requires 'crawl'"):
            orchestrator.validate_stages([Stage.SCRAPE])

    def test_run_with_registered_runners(self, orchestrator):
        def mock_runner(sc):
            return StageResult(stage="crawl", success=True, file_count=5)

        orchestrator.register(Stage.CRAWL, mock_runner)
        results = orchestrator.run([Stage.CRAWL])
        assert Stage.CRAWL in results
        assert results[Stage.CRAWL].success

    def test_run_unregistered_stage_skips(self, orchestrator):
        results = orchestrator.run([Stage.ARCHIVE])
        assert Stage.ARCHIVE not in results

    def test_run_handles_exception(self, orchestrator):
        def failing_runner(sc):
            raise RuntimeError("Boom")

        orchestrator.register(Stage.ARCHIVE, failing_runner)
        results = orchestrator.run([Stage.ARCHIVE])
        assert not results[Stage.ARCHIVE].success
        assert "Boom" in results[Stage.ARCHIVE].errors[0]


class TestDomainFromUrl:
    def test_basic(self):
        assert domain_from_url("https://example.com") == "example.com"

    def test_with_path(self):
        assert domain_from_url("https://example.com/path") == "example.com"

    def test_with_www(self):
        assert domain_from_url("https://www.example.com") == "www.example.com"
