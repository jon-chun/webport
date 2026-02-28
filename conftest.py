"""
WebPort Test Configuration

Shared fixtures and configuration for tests.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import AsyncIterator, Iterator

import pytest
import pytest_asyncio

from webport.core.config import WebPortConfig
from webport.core.models import CrawledPage, PageContent, PageMetadata


# ============================================
# Async Event Loop
# ============================================

@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ============================================
# Temporary Directories
# ============================================

@pytest.fixture
def temp_dir() -> Iterator[Path]:
    """Create temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def output_dir(temp_dir: Path) -> Path:
    """Create output directory."""
    output = temp_dir / "output"
    output.mkdir()
    return output


@pytest.fixture
def checkpoint_dir(temp_dir: Path) -> Path:
    """Create checkpoint directory."""
    checkpoint = temp_dir / "checkpoints"
    checkpoint.mkdir()
    return checkpoint


# ============================================
# Configuration Fixtures
# ============================================

@pytest.fixture
def base_config(temp_dir: Path) -> WebPortConfig:
    """Create base configuration for tests."""
    return WebPortConfig(
        target_url="https://example.com",
        output_dir=temp_dir / "output",
    )


@pytest.fixture
def wordpress_config(base_config: WebPortConfig) -> WebPortConfig:
    """Configuration for WordPress testing."""
    base_config.wordpress.username = "test"
    base_config.wordpress.api_base = "/wp-json"
    return base_config


# ============================================
# Sample Data Fixtures
# ============================================

@pytest.fixture
def sample_html() -> str:
    """Sample HTML page for testing."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="description" content="Test page description">
    <meta property="og:title" content="OG Title">
    <meta property="og:image" content="https://example.com/image.jpg">
    <title>Test Page Title</title>
    <link rel="canonical" href="https://example.com/test">
</head>
<body>
    <header>
        <nav>
            <a href="/">Home</a>
            <a href="/about">About</a>
            <a href="/contact">Contact</a>
        </nav>
    </header>
    <main>
        <h1>Main Heading</h1>
        <p>This is the main content of the page.</p>
        <h2>Subheading</h2>
        <p>More content here with <a href="/link">a link</a>.</p>
        <img src="/images/test.jpg" alt="Test image">
    </main>
    <footer>
        <p>Footer content</p>
    </footer>
</body>
</html>"""


@pytest.fixture
def sample_page_metadata() -> PageMetadata:
    """Sample page metadata."""
    return PageMetadata(
        title="Test Page",
        description="Test description",
        og_title="OG Title",
        og_image="https://example.com/image.jpg",
        canonical_url="https://example.com/test",
        keywords=["test", "sample"],
    )


@pytest.fixture
def sample_page_content(sample_html: str) -> PageContent:
    """Sample page content."""
    return PageContent(
        raw_html=sample_html,
        text_content="Main Heading This is the main content of the page.",
        word_count=10,
        reading_time_minutes=0.05,
        headings=[
            {"level": 1, "text": "Main Heading"},
            {"level": 2, "text": "Subheading"},
        ],
        links=[
            {"href": "/", "text": "Home"},
            {"href": "/about", "text": "About"},
        ],
        images=[
            {"src": "/images/test.jpg", "alt": "Test image"},
        ],
    )


@pytest.fixture
def sample_crawled_page(
    sample_page_metadata: PageMetadata,
    sample_page_content: PageContent,
) -> CrawledPage:
    """Sample crawled page."""
    return CrawledPage(
        url="https://example.com/test",
        final_url="https://example.com/test",
        status_code=200,
        content_type="text/html",
        depth=1,
        response_time_ms=150.0,
        metadata=sample_page_metadata,
        content=sample_page_content,
    )


# ============================================
# Mock Servers
# ============================================

@pytest_asyncio.fixture
async def mock_http_server():
    """Start mock HTTP server for testing."""
    # For integration tests - would use aiohttp test server
    # Placeholder for now
    yield None


# ============================================
# WordPress Fixtures
# ============================================

@pytest.fixture
def wordpress_post_data() -> dict:
    """Sample WordPress API post data."""
    return {
        "id": 1,
        "slug": "test-post",
        "status": "publish",
        "type": "post",
        "title": {"rendered": "Test Post Title"},
        "content": {"rendered": "<p>Post content</p>"},
        "excerpt": {"rendered": "<p>Post excerpt</p>"},
        "author": 1,
        "date": "2024-01-15T10:00:00",
        "modified": "2024-01-15T12:00:00",
        "link": "https://example.com/test-post",
        "featured_media": 0,
        "categories": [1, 2],
        "tags": [3],
        "meta": {},
    }


@pytest.fixture
def wordpress_category_data() -> dict:
    """Sample WordPress API category data."""
    return {
        "id": 1,
        "name": "Test Category",
        "slug": "test-category",
        "description": "Category description",
        "parent": 0,
        "count": 5,
        "link": "https://example.com/category/test-category",
    }


# ============================================
# Markers
# ============================================

def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow")
    config.addinivalue_line("markers", "integration: marks integration tests")
    config.addinivalue_line("markers", "wordpress: marks WordPress-specific tests")
    config.addinivalue_line("markers", "network: marks tests requiring network")
