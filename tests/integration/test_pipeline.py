"""Integration tests for the pipeline."""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from webport.core.config import SiteConfig
from webport.core.models import StageResult
from webport.pipeline.stages import Stage
from webport.pipeline.orchestrator import PipelineOrchestrator


@pytest.fixture
def fixture_site(tmp_path):
    """Create a site directory with fixture data for integration testing."""
    site_dir = tmp_path / "sites" / "test.com"
    input_dir = site_dir / "input"
    input_dir.mkdir(parents=True)

    # Create minimal fixture data
    posts = [
        {
            "id": 1,
            "slug": "test-post",
            "title": {"rendered": "Test Post"},
            "content": {"rendered": "<p>Content</p>"},
            "excerpt": {"rendered": "Excerpt"},
            "date": "2024-01-01T00:00:00",
            "status": "publish",
            "link": "https://test.com/roundtable/test-post/",
            "categories": [],
            "tags": [],
            "meta": {},
        },
    ]
    participants = [
        {
            "id": 10,
            "slug": "john-doe",
            "title": {"rendered": "John Doe"},
            "content": {"rendered": "<p>Bio</p>"},
            "link": "https://test.com/participants/john-doe/",
        },
    ]
    categories = [{"id": 1, "name": "Science", "slug": "science"}]
    tags = [{"id": 1, "name": "Physics", "slug": "physics"}]
    pages = [
        {
            "id": 100,
            "slug": "about",
            "title": {"rendered": "About"},
            "content": {"rendered": "<p>About us</p>"},
            "parent": 0,
        },
    ]
    site_info = {"name": "Test Site", "url": "https://test.com"}

    (input_dir / "wp_posts.json").write_text(json.dumps(posts))
    (input_dir / "wp_participants.json").write_text(json.dumps(participants))
    (input_dir / "wp_categories.json").write_text(json.dumps(categories))
    (input_dir / "wp_tags.json").write_text(json.dumps(tags))
    (input_dir / "wp_pages.json").write_text(json.dumps(pages))
    (input_dir / "wp_media.json").write_text(json.dumps([]))
    (input_dir / "wp_site_info.json").write_text(json.dumps(site_info))
    (input_dir / "roundtable_participants.json").write_text(json.dumps([]))
    (input_dir / "participant_titles.json").write_text(json.dumps([]))

    config = SiteConfig(
        domain="test.com",
        base_url="https://test.com",
        name="Test Site",
    )

    return config, site_dir


@pytest.mark.integration
class TestPipelineIntegration:
    """Integration tests for multi-stage pipeline."""

    def test_analyze_stage_with_fixture_data(self, fixture_site):
        config, site_dir = fixture_site

        # Patch the sites_dir to point to our tmp fixture
        with patch.object(
            type(config), 'sites_dir',
            new_callable=lambda: property(lambda self: site_dir),
        ):
            from webport.analyzers.doc_generator import generate_docs
            result = generate_docs(config)

            assert result.success
            assert result.file_count == 6
            assert any("PRD.md" in f for f in result.files_created)

    def test_generate_stage_with_fixture_data(self, fixture_site):
        config, site_dir = fixture_site

        with patch.object(
            type(config), 'sites_dir',
            new_callable=lambda: property(lambda self: site_dir),
        ):
            from webport.generators.base import run_generator
            result = run_generator(config)

            assert result.success
            assert result.file_count > 0
            assert any("package.json" in f for f in result.files_created)
            assert any("layout.tsx" in f for f in result.files_created)

    def test_orchestrator_runs_analyze_and_generate(self, fixture_site):
        config, site_dir = fixture_site

        with patch.object(
            type(config), 'sites_dir',
            new_callable=lambda: property(lambda self: site_dir),
        ):
            console = MagicMock()
            orch = PipelineOrchestrator(config, console)

            from webport.analyzers.doc_generator import generate_docs
            from webport.generators.base import run_generator

            orch.register(Stage.ANALYZE, lambda sc: generate_docs(sc))
            orch.register(Stage.GENERATE, lambda sc: run_generator(sc))

            results = orch.run([Stage.ANALYZE, Stage.GENERATE])

            assert Stage.ANALYZE in results
            assert Stage.GENERATE in results
            assert results[Stage.ANALYZE].success
            assert results[Stage.GENERATE].success

    def test_full_pipeline_skips_unregistered(self, fixture_site):
        config, _ = fixture_site
        console = MagicMock()
        orch = PipelineOrchestrator(config, console)

        # Only register archive (which always passes dep check)
        orch.register(Stage.ARCHIVE, lambda sc: StageResult(
            stage="archive", success=True, file_count=1,
        ))

        results = orch.run([Stage.ARCHIVE])
        assert results[Stage.ARCHIVE].success
