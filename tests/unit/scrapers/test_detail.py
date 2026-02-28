"""Tests for the detail scraper."""

import json
import pytest

from webport.core.config import (
    SiteConfig,
    DetailScrapeConfig,
    SelectorConfig,
)
from webport.scrapers.detail import DetailScraper


@pytest.fixture
def detail_config():
    return DetailScrapeConfig(
        source_json="wp_participants.json",
        url_field="link",
        fields={
            "professional_title": SelectorConfig(
                selectors=["h1 + p", ".participant-title"],
                transform="strip",
            ),
        },
        output_file="participant_titles.json",
    )


class TestDetailScraper:
    """Test supplemental field extraction."""

    def test_detail_config_validation(self, detail_config):
        assert detail_config.source_json == "wp_participants.json"
        assert "professional_title" in detail_config.fields
        assert detail_config.output_file == "participant_titles.json"

    def test_detail_config_requires_all_fields(self):
        """DetailScrapeConfig requires source_json, fields, and output_file."""
        with pytest.raises(Exception):
            # Missing required fields
            DetailScrapeConfig(source_json="test.json")

    def test_detail_config_selector_chain(self, detail_config):
        title_selector = detail_config.fields["professional_title"]
        assert len(title_selector.selectors) == 2
        assert title_selector.transform == "strip"
