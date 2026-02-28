"""Tests for the CSS selector engine."""

import pytest
from bs4 import BeautifulSoup

from webport.core.config import SelectorConfig
from webport.scrapers.base import SelectorEngine


@pytest.fixture
def roundtable_html():
    from pathlib import Path
    html_path = Path(__file__).parent.parent.parent / "fixtures" / "html" / "roundtable.html"
    return html_path.read_text()


@pytest.fixture
def participant_html():
    from pathlib import Path
    html_path = Path(__file__).parent.parent.parent / "fixtures" / "html" / "participant.html"
    return html_path.read_text()


@pytest.fixture
def roundtable_engine(roundtable_html):
    soup = BeautifulSoup(roundtable_html, "html.parser")
    return SelectorEngine(soup)


@pytest.fixture
def participant_engine(participant_html):
    soup = BeautifulSoup(participant_html, "html.parser")
    return SelectorEngine(soup)


class TestSelectorEngine:
    """Test CSS selector evaluation with fallback chains."""

    def test_select_single_text(self, roundtable_engine):
        config = SelectorConfig(selectors=["h1"])
        result = roundtable_engine.select(config)
        assert result == "Consciousness and the Brain"

    def test_select_single_attribute(self, roundtable_engine):
        config = SelectorConfig(
            selectors=["time[datetime]"],
            attribute="datetime",
        )
        result = roundtable_engine.select(config)
        assert result == "2024-03-15T18:00:00"

    def test_select_multiple_links(self, roundtable_engine):
        config = SelectorConfig(
            selectors=[".participants-list a[href*='/participants/']"],
            attribute="href",
            multiple=True,
        )
        result = roundtable_engine.select(config)
        assert isinstance(result, list)
        assert len(result) == 3
        assert "jane-smith" in result[0]

    def test_select_multiple_text(self, roundtable_engine):
        config = SelectorConfig(
            selectors=[".participants-list a"],
            multiple=True,
        )
        result = roundtable_engine.select(config)
        assert isinstance(result, list)
        assert "Dr. Jane Smith" in result

    def test_fallback_selectors(self, roundtable_engine):
        config = SelectorConfig(
            selectors=[".nonexistent", ".also-nonexistent", "h1"],
        )
        result = roundtable_engine.select(config)
        assert result == "Consciousness and the Brain"

    def test_no_match_returns_none(self, roundtable_engine):
        config = SelectorConfig(selectors=[".nonexistent-class"])
        result = roundtable_engine.select(config)
        assert result is None

    def test_no_match_multiple_returns_empty(self, roundtable_engine):
        config = SelectorConfig(
            selectors=[".nonexistent-class"],
            multiple=True,
        )
        result = roundtable_engine.select(config)
        assert result == []

    def test_transform_strip(self, participant_engine):
        config = SelectorConfig(
            selectors=["h1 + p"],
            transform="strip",
        )
        result = participant_engine.select(config)
        assert result == "Professor of Philosophy, Columbia University"

    def test_select_iframe_src(self, roundtable_engine):
        config = SelectorConfig(
            selectors=["iframe[src*='youtube']"],
            attribute="src",
        )
        result = roundtable_engine.select(config)
        assert result == "https://www.youtube.com/embed/abc123"

    def test_participant_roundtable_links(self, participant_engine):
        config = SelectorConfig(
            selectors=[".roundtables-list a[href*='/roundtable/']"],
            attribute="href",
            multiple=True,
        )
        result = participant_engine.select(config)
        assert isinstance(result, list)
        assert len(result) == 2
        assert "consciousness-2024" in result[0]
