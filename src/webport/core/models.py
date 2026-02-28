"""
WebPort Data Models

Pydantic models for data validation and serialization.

Addresses Critique #10: Pydantic Models Undefined
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union
from pydantic import BaseModel, Field, HttpUrl, field_validator


class ContentType(str, Enum):
    POST = "post"
    PAGE = "page"
    MEDIA = "media"
    CATEGORY = "category"
    TAG = "tag"
    MENU = "menu"
    USER = "user"
    COMMENT = "comment"
    CUSTOM = "custom"


class MediaType(str, Enum):
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    OTHER = "other"


class PageMetadata(BaseModel):
    """Metadata extracted from a page."""
    
    title: Optional[str] = None
    description: Optional[str] = None
    canonical_url: Optional[str] = None
    og_title: Optional[str] = None
    og_description: Optional[str] = None
    og_image: Optional[str] = None
    twitter_card: Optional[str] = None
    robots: Optional[str] = None
    author: Optional[str] = None
    published_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    language: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    custom: Dict[str, Any] = Field(default_factory=dict)


class PageContent(BaseModel):
    """Extracted content from a page."""
    
    raw_html: str
    text_content: str
    main_content: Optional[str] = None
    excerpt: Optional[str] = None
    word_count: int = 0
    reading_time_minutes: float = 0.0
    headings: List[Dict[str, str]] = Field(default_factory=list)
    links: List[Dict[str, str]] = Field(default_factory=list)
    images: List[Dict[str, str]] = Field(default_factory=list)


class CrawledPage(BaseModel):
    """A crawled page with all extracted data."""
    
    url: str
    final_url: Optional[str] = None
    status_code: int
    content_type: str = "text/html"
    content_hash: Optional[str] = None
    
    # Timing
    crawled_at: datetime = Field(default_factory=datetime.utcnow)
    response_time_ms: float = 0.0
    
    # Navigation
    depth: int = 0
    parent_url: Optional[str] = None
    
    # Content
    metadata: PageMetadata = Field(default_factory=PageMetadata)
    content: Optional[PageContent] = None
    
    # Errors
    error: Optional[str] = None
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class MediaItem(BaseModel):
    """A media item (image, video, etc.)."""
    
    url: str
    source_url: str
    local_path: Optional[str] = None
    media_type: MediaType = MediaType.IMAGE
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    alt_text: Optional[str] = None
    title: Optional[str] = None
    caption: Optional[str] = None
    downloaded: bool = False
    error: Optional[str] = None


class WordPressPost(BaseModel):
    """WordPress post/page data."""
    
    id: int
    type: str = "post"
    slug: str
    title: str
    content: str
    excerpt: Optional[str] = None
    status: str = "publish"
    author_id: Optional[int] = None
    author_name: Optional[str] = None
    date: Optional[datetime] = None
    modified: Optional[datetime] = None
    link: Optional[str] = None
    featured_media_id: Optional[int] = None
    featured_media_url: Optional[str] = None
    categories: List[int] = Field(default_factory=list)
    tags: List[int] = Field(default_factory=list)
    meta: Dict[str, Any] = Field(default_factory=dict)
    acf: Dict[str, Any] = Field(default_factory=dict)
    yoast_seo: Dict[str, Any] = Field(default_factory=dict)


class WordPressCategory(BaseModel):
    """WordPress category."""
    
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    parent: int = 0
    count: int = 0
    link: Optional[str] = None


class WordPressTag(BaseModel):
    """WordPress tag."""
    
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    count: int = 0
    link: Optional[str] = None


class WordPressMenu(BaseModel):
    """WordPress menu."""
    
    id: int
    name: str
    slug: str
    items: List["WordPressMenuItem"] = Field(default_factory=list)


class WordPressMenuItem(BaseModel):
    """WordPress menu item."""
    
    id: int
    title: str
    url: str
    menu_order: int = 0
    parent: int = 0
    object_type: Optional[str] = None
    object_id: Optional[int] = None
    children: List["WordPressMenuItem"] = Field(default_factory=list)


class WordPressUser(BaseModel):
    """WordPress user."""
    
    id: int
    name: str
    slug: str
    description: Optional[str] = None
    link: Optional[str] = None
    avatar_urls: Dict[str, str] = Field(default_factory=dict)


class SiteStructure(BaseModel):
    """Overall site structure analysis."""
    
    base_url: str
    total_pages: int = 0
    total_posts: int = 0
    total_media: int = 0
    
    # Navigation
    main_menu: Optional[WordPressMenu] = None
    footer_menu: Optional[WordPressMenu] = None
    
    # Taxonomy
    categories: List[WordPressCategory] = Field(default_factory=list)
    tags: List[WordPressTag] = Field(default_factory=list)
    
    # Users
    authors: List[WordPressUser] = Field(default_factory=list)
    
    # URL patterns
    url_patterns: Dict[str, int] = Field(default_factory=dict)
    
    # Detected features
    has_blog: bool = False
    has_shop: bool = False
    has_search: bool = False
    has_comments: bool = False


class CrawlResult(BaseModel):
    """Complete result of a crawl operation."""
    
    target_url: str
    site_type: str
    crawl_id: str
    
    # Timing
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Stats
    pages_crawled: int = 0
    pages_failed: int = 0
    media_downloaded: int = 0
    
    # Data
    pages: List[CrawledPage] = Field(default_factory=list)
    media: List[MediaItem] = Field(default_factory=list)
    structure: Optional[SiteStructure] = None
    
    # WordPress specific
    posts: List[WordPressPost] = Field(default_factory=list)
    
    # Output
    output_path: Optional[str] = None
    
    # Errors
    errors: List[str] = Field(default_factory=list)


class MigrationResult(BaseModel):
    """Result of migration operation."""
    
    source_url: str
    target_framework: str
    output_path: str
    
    # Timing
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    
    # Stats
    pages_generated: int = 0
    components_generated: int = 0
    assets_copied: int = 0
    
    # Files
    files_created: List[str] = Field(default_factory=list)
    
    # Warnings
    warnings: List[str] = Field(default_factory=list)
    
    # Success
    success: bool = True


class ScrapeResult(BaseModel):
    """Result of a scraping operation."""

    source_file: str
    output_file: str
    items_processed: int = 0
    items_scraped: int = 0
    items_failed: int = 0
    duration_seconds: float = 0.0
    errors: List[str] = Field(default_factory=list)


class StageResult(BaseModel):
    """Result of a pipeline stage execution."""

    stage: str
    success: bool = True
    duration_seconds: float = 0.0
    files_created: List[str] = Field(default_factory=list)
    file_count: int = 0
    errors: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Rebuild model for self-referential types
WordPressMenuItem.model_rebuild()
WordPressMenu.model_rebuild()


__all__ = [
    "ContentType", "MediaType", "PageMetadata", "PageContent", "CrawledPage",
    "MediaItem", "WordPressPost", "WordPressCategory", "WordPressTag",
    "WordPressMenu", "WordPressMenuItem", "WordPressUser", "SiteStructure",
    "CrawlResult", "MigrationResult", "ScrapeResult", "StageResult",
]
