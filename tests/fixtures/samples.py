"""
Test fixtures for WebPort tests.
"""

import json
from pathlib import Path

# Sample HTML content
SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
    <meta name="description" content="A test page">
    <meta property="og:title" content="Test OG Title">
    <link rel="canonical" href="https://example.com/test">
</head>
<body>
    <h1>Welcome</h1>
    <p>This is a test page with some content.</p>
    <a href="/page1">Link 1</a>
    <a href="/page2">Link 2</a>
    <img src="/image.jpg" alt="Test image">
</body>
</html>
"""

# Sample robots.txt
SAMPLE_ROBOTS_TXT = """# Sample robots.txt
User-agent: *
Disallow: /admin/
Disallow: /private/
Allow: /public/
Crawl-delay: 2

User-agent: Googlebot
Disallow: /nogoogle/

Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/sitemap-posts.xml
"""

# Sample sitemap XML
SAMPLE_SITEMAP_XML = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url>
        <loc>https://example.com/</loc>
        <lastmod>2024-01-01</lastmod>
        <changefreq>daily</changefreq>
        <priority>1.0</priority>
    </url>
    <url>
        <loc>https://example.com/about</loc>
        <lastmod>2024-01-02</lastmod>
        <changefreq>monthly</changefreq>
        <priority>0.8</priority>
    </url>
    <url>
        <loc>https://example.com/blog/post-1</loc>
        <lastmod>2024-01-03</lastmod>
    </url>
</urlset>
"""

# Sample sitemap index
SAMPLE_SITEMAP_INDEX = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <sitemap>
        <loc>https://example.com/sitemap-posts.xml</loc>
        <lastmod>2024-01-01</lastmod>
    </sitemap>
    <sitemap>
        <loc>https://example.com/sitemap-pages.xml</loc>
        <lastmod>2024-01-01</lastmod>
    </sitemap>
</sitemapindex>
"""

# Sample WordPress API responses
SAMPLE_WP_POSTS = [
    {
        "id": 1,
        "slug": "hello-world",
        "title": {"rendered": "Hello World"},
        "content": {"rendered": "<p>Welcome to WordPress.</p>"},
        "excerpt": {"rendered": "<p>Welcome...</p>"},
        "status": "publish",
        "author": 1,
        "date": "2024-01-01T12:00:00",
        "modified": "2024-01-02T12:00:00",
        "link": "https://example.com/hello-world",
        "categories": [1],
        "tags": [1, 2],
    },
    {
        "id": 2,
        "slug": "second-post",
        "title": {"rendered": "Second Post"},
        "content": {"rendered": "<p>Another post.</p>"},
        "excerpt": {"rendered": "<p>Another...</p>"},
        "status": "publish",
        "author": 1,
        "date": "2024-01-05T12:00:00",
        "link": "https://example.com/second-post",
        "categories": [2],
        "tags": [],
    },
]

SAMPLE_WP_CATEGORIES = [
    {
        "id": 1,
        "name": "Uncategorized",
        "slug": "uncategorized",
        "description": "",
        "parent": 0,
        "count": 1,
    },
    {
        "id": 2,
        "name": "News",
        "slug": "news",
        "description": "Latest news",
        "parent": 0,
        "count": 1,
    },
]

# Sample configuration
SAMPLE_CONFIG_YAML = """
target:
  url: "https://example.com"
  type: auto

ethics:
  respect_robots_txt: true
  rate_limit: 2.0
  user_agent: "WebPort/1.0"

crawler:
  max_pages: 100
  max_depth: 5
  timeout: 30

migration:
  target: nextjs
  typescript: true
  styling: tailwind
"""


def get_fixture_path(name: str) -> Path:
    """Get path to a fixture file."""
    return Path(__file__).parent / name


def load_json_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    with open(get_fixture_path(name)) as f:
        return json.load(f)
