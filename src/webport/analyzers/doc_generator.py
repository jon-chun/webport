"""Template-based documentation generator from crawl data."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from webport.analyzers.base import BaseAnalyzer
from webport.core.config import SiteConfig
from webport.core.models import StageResult

logger = logging.getLogger(__name__)


class DocGenerator(BaseAnalyzer):
    """Generate documentation from crawled site data.

    Produces Markdown docs: PRD, data-dictionary, database-schema,
    tech-spec, component-inventory, deployment.
    """

    def analyze(self) -> StageResult:
        """Generate all configured documentation files."""
        docs_dir = self.site_config.docs_dir
        docs_dir.mkdir(parents=True, exist_ok=True)

        files_created: List[str] = []
        errors: List[str] = []

        # Load crawl data
        posts = self.load_json("wp_posts.json") or []
        pages = self.load_json("wp_pages.json") or []
        participants = self.load_json("wp_participants.json") or []
        categories = self.load_json("wp_categories.json") or []
        tags = self.load_json("wp_tags.json") or []
        media = self.load_json("wp_media.json") or []
        site_info = self.load_json("wp_site_info.json") or {}

        context = {
            "domain": self.site_config.domain,
            "name": self.site_config.name or site_info.get("name", self.site_config.domain),
            "base_url": self.site_config.base_url,
            "posts_count": len(posts),
            "pages_count": len(pages),
            "participants_count": len(participants),
            "categories_count": len(categories),
            "tags_count": len(tags),
            "media_count": len(media),
            "site_info": site_info,
            "posts": posts,
            "pages": pages,
            "participants": participants,
            "categories": categories,
            "tags": tags,
        }

        generators = {
            "PRD": self._generate_prd,
            "data-dictionary": self._generate_data_dictionary,
            "database-schema": self._generate_database_schema,
            "tech-spec": self._generate_tech_spec,
            "component-inventory": self._generate_component_inventory,
            "deployment": self._generate_deployment,
        }

        for doc_name in self.site_config.analyze.docs:
            gen = generators.get(doc_name)
            if not gen:
                errors.append(f"Unknown doc type: {doc_name}")
                continue

            try:
                content = gen(context)
                path = docs_dir / f"{doc_name}.md"
                path.write_text(content)
                files_created.append(str(path))
                logger.info(f"Generated {path}")
            except Exception as e:
                errors.append(f"Failed to generate {doc_name}: {e}")
                logger.exception(f"Failed to generate {doc_name}")

        return StageResult(
            stage="analyze",
            success=len(errors) == 0,
            files_created=files_created,
            file_count=len(files_created),
            errors=errors,
        )

    def _generate_prd(self, ctx: Dict[str, Any]) -> str:
        return f"""# Product Requirements Document: {ctx['name']}

## Overview
Migration of {ctx['domain']} from WordPress to a modern web framework.

## Content Summary
- **Pages:** {ctx['pages_count']}
- **Posts/Roundtables:** {ctx['posts_count']}
- **Participants:** {ctx['participants_count']}
- **Categories:** {ctx['categories_count']}
- **Tags:** {ctx['tags_count']}
- **Media Items:** {ctx['media_count']}

## Requirements
1. Preserve all existing content and URL structure
2. Maintain M2M relationships (posts <-> participants)
3. Responsive design with modern UI
4. SEO-friendly with metadata preservation
5. Full-text search capability

## Success Criteria
- All content migrated without data loss
- URL redirects from old structure
- Performance improvement over WordPress
- Accessible (WCAG 2.1 AA)
"""

    def _generate_data_dictionary(self, ctx: Dict[str, Any]) -> str:
        # Analyze fields from actual data
        post_fields = _extract_fields(ctx["posts"][:1]) if ctx["posts"] else "N/A"
        participant_fields = (
            _extract_fields(ctx["participants"][:1]) if ctx["participants"] else "N/A"
        )

        return f"""# Data Dictionary: {ctx['name']}

## Content Types

### Posts / Roundtables
Count: {ctx['posts_count']}
Fields: {post_fields}

### Participants
Count: {ctx['participants_count']}
Fields: {participant_fields}

### Pages
Count: {ctx['pages_count']}

### Categories
Count: {ctx['categories_count']}

### Tags
Count: {ctx['tags_count']}

### Media
Count: {ctx['media_count']}

## Relationships
- Posts <-> Participants (M2M via HTML scraping)
- Posts <-> Categories (M2M via WordPress taxonomy)
- Posts <-> Tags (M2M via WordPress taxonomy)
"""

    def _generate_database_schema(self, ctx: Dict[str, Any]) -> str:
        return f"""# Database Schema: {ctx['name']}

## Tables

### posts
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | WordPress post ID |
| slug | TEXT UNIQUE | URL slug |
| title | TEXT | Post title |
| content | TEXT | HTML content |
| excerpt | TEXT | Short excerpt |
| date | DATETIME | Publication date |
| status | TEXT | publish/draft |
| featured_media_url | TEXT | Featured image URL |

### participants
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | WordPress participant ID |
| slug | TEXT UNIQUE | URL slug |
| title | TEXT | Participant name |
| content | TEXT | Bio HTML |
| professional_title | TEXT | Title/affiliation |

### post_participants (M2M)
| Column | Type | Description |
|--------|------|-------------|
| post_id | INTEGER FK | References posts.id |
| participant_id | INTEGER FK | References participants.id |

### categories
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Category ID |
| name | TEXT | Category name |
| slug | TEXT UNIQUE | URL slug |

### tags
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Tag ID |
| name | TEXT | Tag name |
| slug | TEXT UNIQUE | URL slug |
"""

    def _generate_tech_spec(self, ctx: Dict[str, Any]) -> str:
        return f"""# Technical Specification: {ctx['name']}

## Stack
- **Framework:** Next.js 14 (App Router)
- **Language:** TypeScript
- **Database:** SQLite via Prisma ORM
- **Styling:** Tailwind CSS
- **Deployment:** Node.js with PM2

## Architecture
- Static generation (SSG) for content pages
- Server components for data fetching
- Client components for interactivity (search, filters)
- API routes for search endpoint

## Key Features
- Full-text search across posts and participants
- Alphabetical participant filtering
- Responsive grid layouts
- SEO metadata + JSON-LD structured data
- Audio player for podcast episodes
"""

    def _generate_component_inventory(self, ctx: Dict[str, Any]) -> str:
        return f"""# Component Inventory: {ctx['name']}

## Layout Components
- `Header` — Site navigation with mobile menu
- `Footer` — Site footer with links
- `MobileMenu` — Hamburger menu for mobile

## Page Components
- `RoundtableCard` — Card for roundtable listing
- `RoundtableList` — Grid of roundtable cards
- `ParticipantCard` — Card for participant listing
- `ParticipantGrid` — Grid with alphabet filter
- `AlphabetFilter` — A-Z filter bar
- `AudioPlayer` — Podcast audio player
- `ContactForm` — Contact form with validation

## Shared Components
- `SearchBar` — Site-wide search
- `Pagination` — Page navigation
- `Breadcrumbs` — Breadcrumb navigation
- `SEOJsonLd` — Structured data injection
"""

    def _generate_deployment(self, ctx: Dict[str, Any]) -> str:
        return f"""# Deployment Guide: {ctx['name']}

## Prerequisites
- Node.js 18+
- npm or yarn

## Setup
```bash
cd sites/{ctx['domain']}/output/nextjs
npm install
npx prisma generate
npx prisma db seed
npm run build
```

## Development
```bash
npm run dev
```

## Production
```bash
npm run build
npm start
```

## Environment Variables
- `DATABASE_URL` — SQLite database path
- `NEXT_PUBLIC_SITE_URL` — Public site URL
"""


def _extract_fields(items: List[Dict[str, Any]]) -> str:
    """Extract field names from sample data."""
    if not items:
        return "N/A"
    return ", ".join(sorted(items[0].keys()))


def generate_docs(site_config: SiteConfig) -> StageResult:
    """Convenience function to generate docs."""
    generator = DocGenerator(site_config)
    return generator.analyze()
