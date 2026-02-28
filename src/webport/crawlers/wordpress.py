"""
WebPort WordPress Crawler

Specialized crawler for WordPress sites using the REST API.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional
from urllib.parse import urljoin

import httpx

from webport.core.config import WebPortConfig, WordPressConfig
from webport.core.exceptions import WordPressAPIError, WordPressNotDetectedError
from webport.core.models import (
    CrawledPage,
    WordPressCategory,
    WordPressMenu,
    WordPressMenuItem,
    WordPressPost,
    WordPressTag,
    WordPressUser,
)
from webport.core.retry import with_async_retry
from webport.crawlers.base import BaseCrawler

logger = logging.getLogger(__name__)


class WordPressCrawler(BaseCrawler):
    """
    WordPress-specific crawler using the REST API.
    
    Features:
    - REST API v2 support
    - Authentication (basic, application passwords, JWT)
    - Custom post types
    - ACF and Yoast SEO support
    - Menu extraction
    """
    
    def __init__(
        self,
        config: WebPortConfig,
        wp_config: Optional[WordPressConfig] = None,
    ):
        super().__init__(config)
        self.wp_config = wp_config or config.wordpress
        self._api_base = self._get_api_base()
        self._auth_headers: Dict[str, str] = {}
        
        # WordPress data
        self.posts: List[WordPressPost] = []
        self.pages: List[WordPressPost] = []
        self.categories: List[WordPressCategory] = []
        self.tags: List[WordPressTag] = []
        self.users: List[WordPressUser] = []
        self.menus: List[WordPressMenu] = []
        self.media: List[Dict[str, Any]] = []
    
    def _get_api_base(self) -> str:
        """Get WordPress API base URL."""
        return urljoin(self.base_url, f"{self.wp_config.api_base}/{self.wp_config.api_version}")
    
    def _setup_auth(self) -> None:
        """Setup authentication headers."""
        if self.wp_config.application_password and self.wp_config.username:
            import base64
            creds = f"{self.wp_config.username}:{self.wp_config.application_password.get_secret_value()}"
            encoded = base64.b64encode(creds.encode()).decode()
            self._auth_headers["Authorization"] = f"Basic {encoded}"
        
        elif self.wp_config.jwt_token:
            self._auth_headers["Authorization"] = f"Bearer {self.wp_config.jwt_token.get_secret_value()}"
        
        elif self.wp_config.username and self.wp_config.password:
            import base64
            creds = f"{self.wp_config.username}:{self.wp_config.password.get_secret_value()}"
            encoded = base64.b64encode(creds.encode()).decode()
            self._auth_headers["Authorization"] = f"Basic {encoded}"
    
    async def detect_wordpress(self) -> bool:
        """Check if site is WordPress."""
        try:
            response = await self.client.get(
                self._api_base,
                headers=self._auth_headers,
            )
            return response.status_code == 200
        except Exception:
            return False
    
    async def crawl(self) -> List[CrawledPage]:
        """Crawl WordPress site via REST API."""
        logger.info(f"Starting WordPress crawl of {self.base_url}")
        
        self._setup_auth()
        
        # Verify WordPress
        if not await self.detect_wordpress():
            logger.warning("WordPress REST API not detected, falling back to HTML crawl")
            return await super().crawl()
        
        logger.info("WordPress REST API detected, using API crawl")
        
        # Fetch all content types
        tasks = []
        
        if "posts" in self.wp_config.include:
            tasks.append(self._fetch_posts())
        
        if "pages" in self.wp_config.include:
            tasks.append(self._fetch_pages())
        
        if "categories" in self.wp_config.include:
            tasks.append(self._fetch_categories())
        
        if "tags" in self.wp_config.include:
            tasks.append(self._fetch_tags())
        
        if "users" in self.wp_config.include:
            tasks.append(self._fetch_users())
        
        if "media" in self.wp_config.include:
            tasks.append(self._fetch_media())
        
        if "menus" in self.wp_config.include:
            tasks.append(self._fetch_menus())
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Convert to CrawledPage format for compatibility
        pages = self._convert_to_pages()
        
        logger.info(
            f"WordPress crawl complete: {len(self.posts)} posts, "
            f"{len(self.pages)} pages, {len(self.media)} media items"
        )
        
        return pages
    
    @with_async_retry(max_attempts=3)
    async def _api_get(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> httpx.Response:
        """Make authenticated API request."""
        url = f"{self._api_base}/{endpoint}"
        
        await self.rate_limiter.async_acquire(url)
        
        try:
            response = await self.client.get(
                url,
                params=params,
                headers=self._auth_headers,
            )
            
            if response.status_code >= 400:
                try:
                    error_data = response.json()
                    raise WordPressAPIError(
                        url=url,
                        wp_code=error_data.get("code", "unknown"),
                        wp_message=error_data.get("message", "Unknown error"),
                        status_code=response.status_code,
                    )
                except ValueError:
                    pass
            
            return response
            
        finally:
            self.rate_limiter.release(url)
    
    async def _fetch_paginated(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Fetch all pages of a paginated endpoint."""
        params = params or {}
        params.setdefault("per_page", 100)
        page = 1
        
        while True:
            params["page"] = page
            
            response = await self._api_get(endpoint, params)
            
            if response.status_code != 200:
                break
            
            items = response.json()
            
            if not items:
                break
            
            for item in items:
                yield item
            
            # Check if more pages
            total_pages = int(response.headers.get("X-WP-TotalPages", 1))
            
            if page >= total_pages:
                break
            
            page += 1
    
    async def _fetch_posts(self) -> None:
        """Fetch all posts."""
        logger.info("Fetching WordPress posts...")
        
        params = {"status": "publish"}
        
        if self.wp_config.include_acf:
            params["acf_format"] = "standard"
        
        async for post_data in self._fetch_paginated("posts", params):
            post = self._parse_post(post_data)
            self.posts.append(post)
        
        logger.info(f"Fetched {len(self.posts)} posts")
    
    async def _fetch_pages(self) -> None:
        """Fetch all pages."""
        logger.info("Fetching WordPress pages...")
        
        params = {"status": "publish"}
        
        async for page_data in self._fetch_paginated("pages", params):
            page = self._parse_post(page_data, post_type="page")
            self.pages.append(page)
        
        logger.info(f"Fetched {len(self.pages)} pages")
    
    async def _fetch_categories(self) -> None:
        """Fetch all categories."""
        logger.info("Fetching WordPress categories...")
        
        async for cat_data in self._fetch_paginated("categories"):
            category = WordPressCategory(
                id=cat_data["id"],
                name=cat_data["name"],
                slug=cat_data["slug"],
                description=cat_data.get("description", ""),
                parent=cat_data.get("parent", 0),
                count=cat_data.get("count", 0),
                link=cat_data.get("link"),
            )
            self.categories.append(category)
        
        logger.info(f"Fetched {len(self.categories)} categories")
    
    async def _fetch_tags(self) -> None:
        """Fetch all tags."""
        logger.info("Fetching WordPress tags...")
        
        async for tag_data in self._fetch_paginated("tags"):
            tag = WordPressTag(
                id=tag_data["id"],
                name=tag_data["name"],
                slug=tag_data["slug"],
                description=tag_data.get("description", ""),
                count=tag_data.get("count", 0),
                link=tag_data.get("link"),
            )
            self.tags.append(tag)
        
        logger.info(f"Fetched {len(self.tags)} tags")
    
    async def _fetch_users(self) -> None:
        """Fetch all users."""
        logger.info("Fetching WordPress users...")
        
        async for user_data in self._fetch_paginated("users"):
            user = WordPressUser(
                id=user_data["id"],
                name=user_data["name"],
                slug=user_data["slug"],
                description=user_data.get("description", ""),
                link=user_data.get("link"),
                avatar_urls=user_data.get("avatar_urls", {}),
            )
            self.users.append(user)
        
        logger.info(f"Fetched {len(self.users)} users")
    
    async def _fetch_media(self) -> None:
        """Fetch all media items."""
        logger.info("Fetching WordPress media...")
        
        async for media_data in self._fetch_paginated("media"):
            self.media.append(media_data)
        
        logger.info(f"Fetched {len(self.media)} media items")
    
    async def _fetch_menus(self) -> None:
        """Fetch navigation menus."""
        logger.info("Fetching WordPress menus...")
        
        # Try WP REST API Menus plugin endpoint
        try:
            response = await self._api_get("menus")
            if response.status_code == 200:
                menus_data = response.json()
                for menu_data in menus_data:
                    menu = await self._fetch_menu_items(menu_data)
                    if menu:
                        self.menus.append(menu)
        except Exception as e:
            logger.debug(f"Menus endpoint not available: {e}")
        
        # Try wp/v2/menu-items endpoint (WordPress 5.9+)
        if not self.menus:
            try:
                locations_response = await self.client.get(
                    f"{self._api_base}/menu-locations",
                    headers=self._auth_headers,
                )
                if locations_response.status_code == 200:
                    locations = locations_response.json()
                    for location, menu_id in locations.items():
                        if menu_id:
                            menu = WordPressMenu(
                                id=menu_id,
                                name=location,
                                slug=location,
                            )
                            self.menus.append(menu)
            except Exception:
                pass
        
        logger.info(f"Fetched {len(self.menus)} menus")
    
    async def _fetch_menu_items(self, menu_data: Dict) -> Optional[WordPressMenu]:
        """Fetch items for a menu."""
        try:
            menu = WordPressMenu(
                id=menu_data.get("id", 0),
                name=menu_data.get("name", ""),
                slug=menu_data.get("slug", ""),
            )
            
            # Fetch menu items
            response = await self._api_get(f"menus/{menu.id}")
            if response.status_code == 200:
                items_data = response.json().get("items", [])
                menu.items = self._build_menu_tree(items_data)
            
            return menu
            
        except Exception as e:
            logger.debug(f"Error fetching menu: {e}")
            return None
    
    def _build_menu_tree(self, items: List[Dict]) -> List[WordPressMenuItem]:
        """Build hierarchical menu structure."""
        items_by_id: Dict[int, WordPressMenuItem] = {}
        root_items: List[WordPressMenuItem] = []
        
        # First pass: create all items
        for item_data in items:
            item = WordPressMenuItem(
                id=item_data.get("id", 0),
                title=item_data.get("title", ""),
                url=item_data.get("url", ""),
                menu_order=item_data.get("menu_order", 0),
                parent=item_data.get("parent", 0),
                object_type=item_data.get("object"),
                object_id=item_data.get("object_id"),
            )
            items_by_id[item.id] = item
        
        # Second pass: build tree
        for item in items_by_id.values():
            if item.parent and item.parent in items_by_id:
                items_by_id[item.parent].children.append(item)
            else:
                root_items.append(item)
        
        # Sort by menu_order
        root_items.sort(key=lambda x: x.menu_order)
        for item in items_by_id.values():
            item.children.sort(key=lambda x: x.menu_order)
        
        return root_items
    
    def _parse_post(self, data: Dict, post_type: str = "post") -> WordPressPost:
        """Parse WordPress post/page data."""
        # Extract Yoast SEO data
        yoast_data = {}
        if self.wp_config.include_yoast_seo:
            yoast_data = data.get("yoast_head_json", {}) or {}
        
        # Extract ACF data
        acf_data = {}
        if self.wp_config.include_acf:
            acf_data = data.get("acf", {}) or {}
        
        return WordPressPost(
            id=data["id"],
            type=post_type,
            slug=data["slug"],
            title=data["title"].get("rendered", ""),
            content=data["content"].get("rendered", ""),
            excerpt=data.get("excerpt", {}).get("rendered", ""),
            status=data.get("status", "publish"),
            author_id=data.get("author"),
            date=data.get("date"),
            modified=data.get("modified"),
            link=data.get("link"),
            featured_media_id=data.get("featured_media"),
            categories=data.get("categories", []),
            tags=data.get("tags", []),
            meta=data.get("meta", {}),
            acf=acf_data,
            yoast_seo=yoast_data,
        )
    
    def _convert_to_pages(self) -> List[CrawledPage]:
        """Convert WordPress data to CrawledPage format."""
        pages = []
        
        for post in self.posts + self.pages:
            page = CrawledPage(
                url=post.link or f"{self.base_url}/{post.slug}",
                status_code=200,
                content_type="text/html",
            )
            pages.append(page)
        
        return pages
    
    async def _process_page(self, page: CrawledPage) -> None:
        """Process a crawled page."""
        pass  # WordPress data is already structured


__all__ = ["WordPressCrawler"]
