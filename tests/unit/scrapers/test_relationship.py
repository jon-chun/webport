"""Tests for the relationship scraper."""

import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

from webport.core.config import (
    SiteConfig,
    ScrapeConfig,
    RelationshipScrapeConfig,
    SelectorConfig,
)
from webport.scrapers.relationship import RelationshipScraper


@pytest.fixture
def site_config(tmp_path):
    input_dir = tmp_path / "sites" / "example.com" / "input"
    input_dir.mkdir(parents=True)

    # Create source data
    posts = [
        {"slug": "roundtable-1", "link": "https://example.com/roundtable/roundtable-1/"},
        {"slug": "roundtable-2", "link": "https://example.com/roundtable/roundtable-2/"},
    ]
    (input_dir / "wp_posts.json").write_text(json.dumps(posts))

    config = SiteConfig(
        domain="example.com",
        base_url="https://example.com",
    )
    # Override the sites_dir to use tmp_path
    config.__dict__["_sites_dir_override"] = tmp_path / "sites" / "example.com"
    return config


@pytest.fixture
def rel_config():
    return RelationshipScrapeConfig(
        source_json="wp_posts.json",
        url_field="link",
        target_container=SelectorConfig(
            selectors=[".participants-list"],
        ),
        target_link=SelectorConfig(
            selectors=[".participants-list a"],
            attribute="href",
            multiple=True,
        ),
        target_name=SelectorConfig(
            selectors=[".participants-list a"],
            multiple=True,
        ),
        output_file="roundtable_participants.json",
    )


@pytest.fixture
def roundtable_html():
    return Path(__file__).parent.parent.parent / "fixtures" / "html" / "roundtable.html"


class TestRelationshipScraper:
    """Test M2M relationship extraction."""

    def test_rel_config_validation(self, rel_config):
        assert rel_config.source_json == "wp_posts.json"
        assert rel_config.output_file == "roundtable_participants.json"
        assert len(rel_config.target_link.selectors) == 1

    def test_rel_config_requires_all_fields(self):
        """RelationshipScrapeConfig requires source_json, target_container, target_link, output_file."""
        with pytest.raises(Exception):
            # Missing required fields
            RelationshipScrapeConfig(source_json="test.json")
