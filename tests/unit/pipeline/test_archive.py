"""Tests for the archive stage."""

import json
import zipfile
import pytest
from pathlib import Path
from unittest.mock import patch

from webport.core.config import SiteConfig
from webport.pipeline.archive import create_archive, should_exclude


@pytest.fixture
def site_with_data(tmp_path):
    """Create a temporary site directory with test data."""
    site_dir = tmp_path / "sites" / "example.com"
    input_dir = site_dir / "input"
    output_dir = site_dir / "output" / "docs"
    input_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    # Create test files
    (input_dir / "wp_posts.json").write_text(json.dumps([{"id": 1}]))
    (input_dir / "wp_pages.json").write_text(json.dumps([{"id": 2}]))
    (output_dir / "PRD.md").write_text("# PRD")

    # Create files that should be excluded
    nm_dir = site_dir / "output" / "nextjs" / "node_modules" / "pkg"
    nm_dir.mkdir(parents=True)
    (nm_dir / "index.js").write_text("module.exports = {}")

    config = SiteConfig(
        domain="example.com",
        base_url="https://example.com",
    )

    # Patch the sites_dir property
    with patch.object(type(config), 'sites_dir', new_callable=lambda: property(lambda self: site_dir)):
        yield config, site_dir


class TestShouldExclude:
    def test_node_modules_excluded(self):
        assert should_exclude(Path("output/nextjs/node_modules/pkg/index.js"))

    def test_next_dir_excluded(self):
        assert should_exclude(Path("output/nextjs/.next/cache/file"))

    def test_env_excluded(self):
        assert should_exclude(Path("output/nextjs/.env"))

    def test_normal_file_not_excluded(self):
        assert not should_exclude(Path("input/wp_posts.json"))

    def test_docs_not_excluded(self):
        assert not should_exclude(Path("output/docs/PRD.md"))

    def test_ds_store_excluded(self):
        assert should_exclude(Path("input/.DS_Store"))


class TestCreateArchive:
    def test_missing_site_dir(self):
        config = SiteConfig(domain="nonexistent.com", base_url="https://nonexistent.com")
        result = create_archive(config)
        assert not result.success
        assert "not found" in result.errors[0]
