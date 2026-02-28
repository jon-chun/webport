"""Tests for SiteConfig and related configuration models."""

import pytest
import yaml
from pathlib import Path

from webport.core.config import (
    SiteConfig,
    ScrapeConfig,
    SelectorConfig,
    RelationshipScrapeConfig,
    DetailScrapeConfig,
    WPCrawlConfig,
    GenerateConfig,
    AnalyzeConfig,
    MigrationTarget,
)


class TestSelectorConfig:
    def test_basic_selector(self):
        config = SelectorConfig(selectors=["h1"])
        assert config.selectors == ["h1"]
        assert config.attribute is None
        assert config.multiple is False

    def test_with_attribute(self):
        config = SelectorConfig(selectors=["a"], attribute="href", multiple=True)
        assert config.attribute == "href"
        assert config.multiple is True

    def test_with_transform(self):
        config = SelectorConfig(selectors=[".title"], transform="strip")
        assert config.transform == "strip"

    def test_requires_at_least_one_selector(self):
        with pytest.raises(Exception):
            SelectorConfig(selectors=[])

    def test_fallback_chain(self):
        config = SelectorConfig(selectors=[".primary", ".fallback", "h1"])
        assert len(config.selectors) == 3


class TestScrapeConfig:
    def test_defaults(self):
        config = ScrapeConfig()
        assert config.rate_limit_delay == 0.5
        assert config.max_concurrent == 4
        assert config.timeout == 30.0
        assert config.relationships == []
        assert config.details == []

    def test_with_relationship(self):
        config = ScrapeConfig(
            relationships=[
                RelationshipScrapeConfig(
                    source_json="wp_posts.json",
                    target_container=SelectorConfig(selectors=[".list"]),
                    target_link=SelectorConfig(selectors=["a"], attribute="href", multiple=True),
                    output_file="rels.json",
                ),
            ],
        )
        assert len(config.relationships) == 1


class TestWPCrawlConfig:
    def test_defaults(self):
        config = WPCrawlConfig()
        assert config.save_raw_json is True
        assert "posts" in config.include_standard

    def test_custom_post_types(self):
        config = WPCrawlConfig(custom_post_types=["roundtable", "participant"])
        assert "roundtable" in config.custom_post_types


class TestGenerateConfig:
    def test_defaults(self):
        config = GenerateConfig()
        assert config.target == MigrationTarget.NEXTJS
        assert config.typescript is True
        assert config.prisma is True


class TestAnalyzeConfig:
    def test_defaults(self):
        config = AnalyzeConfig()
        assert "PRD" in config.docs
        assert config.use_ai is False


class TestSiteConfig:
    def test_basic_creation(self):
        config = SiteConfig(
            domain="example.com",
            base_url="https://example.com",
        )
        assert config.domain == "example.com"
        assert config.base_url == "https://example.com"

    def test_url_validation(self):
        with pytest.raises(Exception):
            SiteConfig(domain="example.com", base_url="not-a-url")

    def test_url_trailing_slash_stripped(self):
        config = SiteConfig(
            domain="example.com",
            base_url="https://example.com/",
        )
        assert config.base_url == "https://example.com"

    def test_directories(self):
        config = SiteConfig(
            domain="example.com",
            base_url="https://example.com",
        )
        assert config.sites_dir == Path("sites/example.com")
        assert config.input_dir == Path("sites/example.com/input")
        assert config.output_dir == Path("sites/example.com/output")
        assert config.docs_dir == Path("sites/example.com/output/docs")

    def test_from_yaml(self, tmp_path):
        yaml_content = {
            "domain": "test.com",
            "base_url": "https://test.com",
            "name": "Test Site",
            "wordpress": {
                "custom_post_types": ["product"],
            },
        }
        yaml_path = tmp_path / "webport.yaml"
        yaml_path.write_text(yaml.dump(yaml_content))

        config = SiteConfig.from_yaml(yaml_path)
        assert config.domain == "test.com"
        assert config.name == "Test Site"
        assert "product" in config.wordpress.custom_post_types

    def test_full_config_from_yaml(self, tmp_path):
        """Test loading the actual helixcenter.org config."""
        config_path = Path("sites/helixcenter.org/webport.yaml")
        if config_path.exists():
            config = SiteConfig.from_yaml(config_path)
            assert config.domain == "helixcenter.org"
            assert "roundtable" in config.wordpress.custom_post_types
            assert len(config.scrape.relationships) >= 1
            assert len(config.scrape.details) >= 1
