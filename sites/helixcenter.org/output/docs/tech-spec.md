# Technical Specification: The Helix Center Website

**Project:** helixcenter.org WordPress-to-Next.js Migration
**Version:** 1.0
**Date:** 2026-02-27
**Status:** Draft

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Data Model](#3-data-model)
4. [Route Structure](#4-route-structure)
5. [Component Architecture](#5-component-architecture)
6. [Static Generation Strategy](#6-static-generation-strategy)
7. [Search](#7-search)
8. [Audio Handling](#8-audio-handling)
9. [Environment Variables](#9-environment-variables)
10. [Build & Deploy Pipeline](#10-build--deploy-pipeline)
11. [Performance](#11-performance)
12. [Security Considerations](#12-security-considerations)

---

## 1. Overview

### 1.1 Purpose

This document specifies the technical architecture for migrating The Helix Center website (helixcenter.org) from WordPress to a statically generated Next.js application. The Helix Center is an interdisciplinary investigation center that hosts roundtable discussions; the site serves as an archive of 135 roundtables, 519 participants, and associated audio recordings.

### 1.2 Goals

- Replace the WordPress PHP/MySQL stack with a modern TypeScript/Next.js application
- Preserve all existing content, URLs, and SEO equity
- Deliver sub-2-second First Contentful Paint via static generation
- Maintain the existing audio hosting infrastructure at media.helixcenter.org
- Provide full-text search across roundtables and participants without external services
- Simplify hosting and operations with a single VPS deployment

### 1.3 Content Inventory

| Content Type    | Count | Notes                                    |
|-----------------|-------|------------------------------------------|
| Roundtables     | 135   | 127 with audio, 127 with YouTube video, avg 5.5 participants |
| Participants    | 519   | 516 with headshots, 515 with bios        |
| Pages           | 19    | Hierarchical (About has child pages)     |
| Tags            | 513   | Topic tags associated with roundtables   |
| Media assets    | 98    | Images managed via WordPress media API   |
| Series          | --    | Hierarchical taxonomy for roundtables    |

### 1.4 Source Data

All content originates from a WebForge crawl of the WordPress REST API, supplemented by a dedicated HTML scraper (`scrape_missing_data.py`) that fills data gaps not available via the API. The seed data resides in `../../input/` relative to the Prisma directory and includes:

**WordPress REST API data:**

- `wp_posts.json` -- Roundtable post data (custom post type, includes Yoast SEO metadata)
- `wp_participants.json` -- Participant custom post type (includes Yoast SEO metadata)
- `wp_pages.json` -- Static pages
- `wp_tags.json` -- Tag taxonomy
- `wp_media.json` -- Complete media library with pagination (includes captions, filesizes, image size variants)
- `wp_podcasts.json` -- Podcast episodes with audio metadata
- `wp_series.json` -- Series taxonomy with descriptions (via supplemental API scrape)

**HTML-scraped supplemental data:**

- `participant_titles.json` -- Professional titles scraped from individual participant pages (CSS: `h1 + p`), keyed by slug
- `roundtable_details.json` -- Event dates/times (CSS: `p.mb-1`), event status badges (CSS: `span.badge`), and YouTube video embed URLs from iframes, keyed by slug
- `roundtable_participants.json` -- Scraped many-to-many relationships
- `html_participants.json` -- Additional participant data from HTML scraping

**Structural data:**

- `site_structure.json` -- Navigation, footer links, design metadata
- `crawl_summary.json` -- Crawl statistics and validation data

---

## 2. Architecture

### 2.1 Technology Stack

| Layer           | Technology                              |
|-----------------|-----------------------------------------|
| Framework       | Next.js 14 (App Router)                 |
| Language        | TypeScript (strict mode)                |
| Database        | SQLite 3                                |
| ORM             | Prisma (SQLite provider)                |
| Styling         | Tailwind CSS                            |
| Search          | SQLite FTS5 (full-text search)          |
| Audio           | HTML5 `<audio>` element                 |
| Deployment      | Ubuntu VPS + Nginx + PM2 + Let's Encrypt|

### 2.2 Rendering Strategy

The application uses **Static Site Generation (SSG)** exclusively. All pages are pre-rendered at build time using `generateStaticParams()` for dynamic routes. There is no Incremental Static Regeneration (ISR) or server-side rendering at request time -- content changes are deployed via full rebuilds.

The single exception is the `/api/search` route, which runs as a server-side API endpoint querying SQLite FTS5 at request time.

### 2.3 System Diagram

```
                    +-------------------+
                    |   Nginx (443/80)  |
                    |  Let's Encrypt SSL|
                    |  Static cache     |
                    +---------+---------+
                              |
                              | reverse proxy :3000
                              v
                    +---------+---------+
                    |   Next.js (PM2)   |
                    |  Static pages +   |
                    |  /api/search      |
                    +---------+---------+
                              |
                              | Prisma client
                              v
                    +---------+---------+
                    |     SQLite DB     |
                    |  (FTS5 enabled)   |
                    +-------------------+

  Audio/Media:
    Browser ----> media.helixcenter.org (external CDN)
```

### 2.4 Directory Structure

```
helixcenter.org/
├── prisma/
│   ├── schema.prisma         # Database schema
│   ├── seed.ts               # Data import from crawl JSON
│   └── migrations/           # Prisma migrations
├── src/
│   ├── app/                  # Next.js App Router pages
│   │   ├── layout.tsx        # Root layout (Header + Footer)
│   │   ├── page.tsx          # Home page
│   │   ├── roundtables/
│   │   │   ├── page.tsx      # Paginated list
│   │   │   └── [slug]/
│   │   │       └── page.tsx  # Individual roundtable
│   │   ├── participants/
│   │   │   ├── page.tsx      # A-Z grid
│   │   │   └── [slug]/
│   │   │       └── page.tsx  # Individual participant
│   │   ├── about/
│   │   │   ├── page.tsx      # About page
│   │   │   └── [slug]/
│   │   │       └── page.tsx  # Sub-pages
│   │   ├── contact/
│   │   ├── donate/
│   │   ├── community/
│   │   ├── videos/
│   │   ├── search/
│   │   │   └── page.tsx      # Search results (client-side)
│   │   └── api/
│   │       └── search/
│   │           └── route.ts  # FTS5 search endpoint
│   ├── components/           # Shared React components
│   ├── lib/                  # Database helpers, utilities
│   └── styles/               # Tailwind configuration
├── public/                   # Static assets
├── ecosystem.config.js       # PM2 configuration
├── tailwind.config.ts
├── tsconfig.json
├── next.config.js
└── package.json
```

### 2.5 Supplemental Scraper

The WordPress REST API does not expose all required data fields. A supplemental Python scraper (`scrape_missing_data.py`) fills these gaps by fetching individual HTML pages and extracting data via CSS selectors:

| Data Point            | Source Page              | CSS Selector / Method       | Output File                |
|-----------------------|--------------------------|-----------------------------|----------------------------|
| Professional titles   | `/participants/[slug]/`  | `h1 + p` (paragraph after name heading) | `participant_titles.json`  |
| Event date/time       | `/roundtables/[slug]/`   | `p.mb-1`                    | `roundtable_details.json`  |
| Event status          | `/roundtables/[slug]/`   | `span.badge`                | `roundtable_details.json`  |
| YouTube video URL     | `/roundtables/[slug]/`   | `iframe[src*="youtube"]`    | `roundtable_details.json`  |
| Series taxonomy       | WP REST API `/series`    | API endpoint                | `wp_series.json`           |
| Complete media library | WP REST API `/media`    | API with pagination         | `wp_media.json`            |

The scraper outputs JSON files keyed by slug, which the seed script merges with the primary API data during database import.

---

## 3. Data Model

> For the complete database schema including field types, constraints, indexes, and relationships, see [database-schema.md](database-schema.md).

### 3.1 Entity Summary

The Prisma schema defines the following models:

| Model                    | Purpose                                         |
|--------------------------|------------------------------------------------ |
| **Roundtable**           | Core content entity -- roundtable discussion, including event metadata, video embeds, and Yoast SEO fields |
| **Participant**          | Person who participates in roundtables, with professional title and papers metadata |
| **RoundtableParticipant**| Join table: many-to-many roundtable-participant |
| **Tag**                  | Topic tag for roundtables                       |
| **RoundtableTag**        | Join table: many-to-many roundtable-tag         |
| **Page**                 | Static page with self-referential hierarchy     |
| **Media**                | Image/file asset with caption, filesize, and image size variants (JSON) |
| **Series**               | Hierarchical taxonomy grouping roundtables, with description |
| **SiteConfig**           | Key-value store for site-wide settings          |

### 3.1.1 Key Field Additions

The following fields were added to capture data sourced from the supplemental scraper and Yoast SEO metadata:

**Roundtable** (sourced from `roundtable_details.json` + Yoast):

| Field              | Type     | Source            | Description                                      |
|--------------------|----------|-------------------|--------------------------------------------------|
| `eventDatetime`    | String?  | HTML scrape       | Human-readable date, e.g. "October 4th, 2025 at 2:00PM" |
| `eventStatus`      | String?  | HTML scrape       | Badge text: "Past Event" or "Future Event"       |
| `videoUrl`         | String?  | HTML scrape       | YouTube embed URL from iframe on roundtable page |
| `downloadLink`     | String?  | WP API meta       | Podcast download URL                             |
| `playerLink`       | String?  | WP API meta       | Podcast player URL                               |
| `ogDescription`    | String?  | Yoast SEO         | Open Graph description for SEO metadata          |
| `ogImageUrl`       | String?  | Yoast SEO         | Open Graph image URL for social sharing          |
| `canonicalUrl`     | String?  | Yoast SEO         | Canonical URL for SEO                            |
| `audioFilesizeRaw` | String?  | WP API meta       | Raw audio filesize in bytes (as string)          |

**Participant** (sourced from `participant_titles.json` + Yoast):

| Field              | Type     | Source            | Description                                      |
|--------------------|----------|-------------------|--------------------------------------------------|
| `professionalTitle`| String   | HTML scrape       | Title/affiliation, e.g. "Professor, Neuroscience, Icahn School of Medicine" |
| `hasPapers`        | Boolean  | HTML scrape       | Whether the participant page has a papers section |
| `papersText`       | String   | HTML scrape       | Raw text content of papers/presentations section |
| `ogDescription`    | String   | Yoast SEO         | Open Graph description (truncated bio)           |
| `ogImageUrl`       | String   | Yoast SEO         | Open Graph image URL                             |

**Media** (sourced from complete `wp_media.json`):

| Field              | Type     | Source            | Description                                      |
|--------------------|----------|-------------------|--------------------------------------------------|
| `caption`          | String   | WP API            | Media caption (rendered HTML)                    |
| `filesize`         | Int?     | WP API            | File size in bytes                               |
| `sizes`            | String   | WP API            | JSON map of image size variants: `{thumbnail: {url, w, h}, medium: {...}, ...}` |

**Series** (sourced from `wp_series.json`):

| Field              | Type     | Source            | Description                                      |
|--------------------|----------|-------------------|--------------------------------------------------|
| `description`      | String   | WP API            | Taxonomy term description                        |

### 3.2 Key Relationships

```
Roundtable  *--*  Participant    (via RoundtableParticipant join table)
Roundtable  *--*  Tag            (via RoundtableTag join table)
Roundtable  *--1  Series         (optional series membership)
Page        *--1  Page           (self-referential parent/child hierarchy)
```

### 3.3 Seed Process

The seed script (`prisma/seed.ts`) reads crawl JSON files from `../../input/` and merges data from multiple sources. The import order respects foreign key dependencies:

1. **Media** from `wp_media.json` -- includes caption, filesize, and image size variants (serialized as JSON)
2. **Tags** from `wp_tags.json`
3. **Series** from `wp_series.json` (with description); falls back to extracting series from embedded term data in posts if the file is missing
4. **Pages** from `wp_pages.json` -- two-pass import to establish parent-child relationships
5. **Participants** from `wp_participants.json` merged with `participant_titles.json` -- professional titles, papers metadata, and Yoast OG fields are combined at insert time
6. **Roundtables** from `wp_posts.json` merged with `roundtable_details.json` -- event dates, video URLs, and Yoast SEO fields are combined at insert time; audio metadata comes from post meta fields
7. **Roundtable-Tag joins** from tag IDs embedded in post data
8. **Roundtable-Participant joins** from `roundtable_participants.json`
9. **SiteConfig** key-value pairs for site-wide settings

All slug values are derived from WordPress slugs to preserve URL compatibility. The script uses `upsert` operations throughout to ensure idempotency.

---

## 4. Route Structure

### 4.1 Route Table

| Route                        | Type       | Data Source                  | Generation     |
|------------------------------|------------|------------------------------|----------------|
| `/`                          | Static     | Latest roundtable + recent 6 | Build time     |
| `/roundtables`               | Static     | Paginated roundtable list    | Build time     |
| `/roundtables/[slug]`        | Dynamic    | Single roundtable + relations| `generateStaticParams` |
| `/participants`              | Static     | All participants A-Z         | Build time     |
| `/participants/[slug]`       | Dynamic    | Single participant + roundtables | `generateStaticParams` |
| `/about`                     | Static     | Page content                 | Build time     |
| `/about/board-of-directors`  | Static     | Page content                 | Build time     |
| `/about/executive-committee` | Static     | Page content                 | Build time     |
| `/about/[slug]`              | Dynamic    | Child pages of About         | `generateStaticParams` |
| `/contact`                   | Static     | Page content                 | Build time     |
| `/donate`                    | Static     | Page content                 | Build time     |
| `/community`                 | Static     | Page content                 | Build time     |
| `/videos`                    | Static     | Page content                 | Build time     |
| `/search`                    | Client     | Client-side fetch to API     | Build time (shell) |
| `/api/search`                | API Route  | SQLite FTS5 query            | Runtime        |

### 4.2 URL Preservation

All routes mirror the existing WordPress permalink structure to preserve SEO equity and avoid redirects. Roundtable slugs, participant slugs, and page slugs are carried over directly from the WordPress data.

### 4.3 Pagination

The `/roundtables` page uses query-parameter-based pagination (`?page=2`). Each page displays a configurable number of roundtables (default: 12), ordered by date descending. Total page count is computed from the roundtable count at build time.

---

## 5. Component Architecture

> For the complete component inventory including props interfaces, usage patterns, and Tailwind styling details, see [component-inventory.md](component-inventory.md).

### 5.1 Layout Components

- **RootLayout** -- App-wide wrapper providing `<Header>` and `<Footer>`, global styles, and metadata
- **Header** -- Site logo, primary navigation with dropdown for About sub-pages, mobile hamburger menu
- **Footer** -- Social media links (Facebook, Twitter/X, YouTube, Instagram, iTunes), RSS link, contact link, copyright

### 5.2 Content Components

| Component          | Purpose                                                    |
|--------------------|------------------------------------------------------------|
| RoundtableCard     | Preview card: title, event date, event status badge, participant count, audio/video badges |
| RoundtableList     | Grid/list of RoundtableCards with pagination controls       |
| AudioPlayer        | Custom HTML5 audio player with play/pause, progress, duration |
| VideoEmbed         | Responsive 16:9 YouTube iframe embed, rendered when `videoUrl` is present |
| ParticipantCard    | Headshot thumbnail, name, professional title               |
| ParticipantGrid    | Responsive grid of ParticipantCards                        |
| AlphabetFilter     | A-Z letter bar for filtering participants                  |
| ParticipantChips   | Inline horizontal list of participant names on roundtable pages |
| PageContent        | Renders WordPress HTML content with sanitization           |
| SearchBar          | Text input with debounced query to /api/search             |
| Breadcrumbs        | Hierarchical breadcrumb navigation                         |
| SEOJsonLd          | Structured data (JSON-LD) for roundtables and participants |
| OGMetadata         | Open Graph meta tags from Yoast SEO data (ogDescription, ogImageUrl) |
| Pagination         | Page number controls for roundtable list                   |

### 5.3 Component Data Flow

Components receive data as props from server components. Page-level server components query Prisma directly, and pass serialized results to client components where interactivity is required (AudioPlayer, SearchBar, AlphabetFilter, Pagination).

---

## 6. Static Generation Strategy

### 6.1 Build-Time Generation

All content pages are pre-rendered at build time. Dynamic route segments use `generateStaticParams()` to enumerate all valid slugs:

```typescript
// app/roundtables/[slug]/page.tsx
export async function generateStaticParams() {
  const roundtables = await prisma.roundtable.findMany({
    select: { slug: true },
  });
  return roundtables.map((r) => ({ slug: r.slug }));
}
```

This applies to:

- **135** roundtable detail pages
- **519** participant detail pages
- **~6** About sub-pages
- All other static pages

### 6.2 No ISR

Because the content is archival and changes infrequently, Incremental Static Regeneration is not used. Content updates follow the full rebuild pipeline:

1. Re-crawl the source (if needed) or update seed data
2. Re-seed the database
3. Run `npm run build` to regenerate all static pages
4. Restart the PM2 process

### 6.3 Client-Side Hydration

Pages that require client-side interactivity use the `"use client"` directive at the component level, not the page level. This preserves server component benefits (zero JS for static content) while enabling:

- Audio playback controls
- Search input with live results
- Alphabet filtering on the participants page
- Pagination state (if client-side)

### 6.4 Expected Build Output

| Metric              | Estimate                |
|---------------------|-------------------------|
| Total static pages  | ~680                    |
| Build time          | 30-90 seconds           |
| Output size         | ~50-100 MB (HTML + JS)  |

---

## 7. Search

### 7.1 Architecture

Search uses SQLite FTS5 (Full-Text Search version 5), queried via a Next.js API route. This avoids external search services (Algolia, Elasticsearch) and keeps the entire stack self-contained.

### 7.2 FTS5 Virtual Table

A virtual table is created during database setup to index searchable content:

```sql
CREATE VIRTUAL TABLE search_index USING fts5(
  title,
  content,
  entity_type,    -- 'roundtable' | 'participant'
  entity_slug,
  tokenize='porter unicode61'
);
```

The `porter` tokenizer enables stemming (e.g., "investigating" matches "investigation"). The `unicode61` tokenizer handles accented characters common in participant names (e.g., Rabate, Pommier).

### 7.3 API Endpoint

```
GET /api/search?q=<query>&type=<roundtable|participant>&limit=20&offset=0
```

**Parameters:**

| Param  | Type   | Default | Description                          |
|--------|--------|---------|--------------------------------------|
| `q`    | string | --      | Search query (required, min 2 chars) |
| `type` | string | all     | Filter by entity type                |
| `limit`| number | 20      | Results per page                     |
| `offset`| number| 0       | Pagination offset                    |

**Response:**

```json
{
  "results": [
    {
      "title": "The Nature of Consciousness",
      "snippet": "...exploring the <mark>consciousness</mark> problem...",
      "type": "roundtable",
      "slug": "the-nature-of-consciousness",
      "url": "/roundtables/the-nature-of-consciousness"
    }
  ],
  "total": 12,
  "query": "consciousness"
}
```

### 7.4 Client-Side Integration

The `/search` page is a client component that:

1. Reads the `q` query parameter from the URL
2. Debounces input (300ms) before calling `/api/search`
3. Renders results with highlighted matching text
4. Updates the URL query string for shareable search links
5. Shows loading state during fetch

### 7.5 Index Population

The FTS5 index is populated as part of the seed script after all roundtables and participants are inserted. The indexed fields are:

- **Roundtables:** title, content (HTML stripped to plain text)
- **Participants:** name, bio (HTML stripped to plain text)

---

## 8. Audio Handling

### 8.1 Hosting

Audio files (MP3) are hosted externally at `media.helixcenter.org` and are **not** migrated as part of this project. The existing CDN/server continues to serve audio content. URLs follow the pattern:

```
http://media.helixcenter.org/podcasts/audio/<filename>.mp3
```

### 8.2 Metadata

Each roundtable with audio has the following fields stored in the database:

| Field        | Type   | Example                          |
|--------------|--------|----------------------------------|
| `audio_file` | string | Full URL to MP3 file             |
| `duration`   | string | `"1:13:43"` (HH:MM:SS or MM:SS) |
| `filesize`   | string | `"50.61M"` (human-readable)      |
| `filesize_raw`| number| `53073183` (bytes)               |

### 8.3 AudioPlayer Component

The custom AudioPlayer component wraps the HTML5 `<audio>` element with:

- **Play/Pause toggle** -- single button with icon state
- **Progress bar** -- clickable/scrubbable timeline showing elapsed/total time
- **Duration display** -- formatted time from metadata or computed from audio element
- **Loading state** -- visual indicator while audio buffer loads
- **Error handling** -- graceful fallback if audio URL is unreachable

```typescript
interface AudioPlayerProps {
  src: string;          // Full URL to MP3 file
  duration?: string;    // Pre-computed duration string
  title: string;        // Roundtable title for accessibility
}
```

The component uses `"use client"` since it requires browser APIs (`HTMLAudioElement`, `timeupdate` events).

### 8.4 Audio Statistics

- 127 of 135 roundtables have associated audio files
- Average duration: approximately 1-2 hours per roundtable
- All audio is served over HTTP from the external host (not HTTPS)

### 8.5 Video Embeds

127 of 135 roundtables have YouTube video recordings. Video URLs are scraped from iframe elements on the WordPress roundtable pages by the supplemental scraper and stored in the `videoUrl` field on the Roundtable model.

**VideoEmbed component:**

The `VideoEmbed` component renders a responsive 16:9 YouTube iframe when `videoUrl` is present on a roundtable record. It is conditionally rendered on the roundtable detail page:

```typescript
interface VideoEmbedProps {
  url: string;    // YouTube embed URL (e.g., "https://www.youtube.com/embed/...")
  title: string;  // Roundtable title for iframe accessibility
}
```

The component uses a responsive wrapper with `aspect-video` (Tailwind) to maintain a 16:9 aspect ratio across screen sizes. The iframe includes `loading="lazy"` for performance and `allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"` for full YouTube player functionality.

**CSP note:** The Content-Security-Policy header includes `frame-src https://www.youtube.com` to allow YouTube embeds.

---

## 9. Environment Variables

### 9.1 Required Variables

| Variable                  | Value                              | Context      | Description                     |
|---------------------------|------------------------------------|--------------|---------------------------------|
| `DATABASE_URL`            | `file:./dev.db`                    | Server       | SQLite database file path       |
| `NEXT_PUBLIC_SITE_URL`    | `https://helixcenter.org`          | Client + Server | Canonical site URL for SEO   |
| `NEXT_PUBLIC_MEDIA_URL`   | `https://media.helixcenter.org`    | Client + Server | Audio/media CDN base URL     |

### 9.2 Variable Conventions

- Variables prefixed with `NEXT_PUBLIC_` are exposed to the browser bundle and must not contain secrets
- `DATABASE_URL` is server-only and used exclusively by Prisma
- All variables are defined in `.env` at the project root (not committed to version control)
- A `.env.example` file is provided with placeholder values

### 9.3 Environment-Specific Overrides

| Environment  | DATABASE_URL             | SITE_URL                        |
|-------------|--------------------------|----------------------------------|
| Development  | `file:./dev.db`          | `http://localhost:3000`          |
| Production   | `file:./prod.db`         | `https://helixcenter.org`        |

---

## 10. Build & Deploy Pipeline

### 10.1 Build Steps

```bash
# 1. Install dependencies
npm install

# 2. Generate Prisma client from schema
npx prisma generate

# 3. Create/update database tables
npx prisma db push

# 4. Seed database from crawl JSON
npx tsx prisma/seed.ts

# 5. Build Next.js application (static generation)
npm run build
```

### 10.2 Seed Script Details

The seed script (`prisma/seed.ts`) is idempotent -- it uses `upsert` operations throughout to safely re-import from the crawl JSON files. It merges data from multiple source files during import:

1. Import media from `wp_media.json` (caption, filesize, image size variants as JSON)
2. Import tags from `wp_tags.json`
3. Import series from `wp_series.json` (with description; fallback to embedded term data)
4. Import pages with parent-child hierarchy (two-pass)
5. Import participants from `wp_participants.json` + `participant_titles.json` (merges professional titles, papers, Yoast OG)
6. Import roundtables from `wp_posts.json` + `roundtable_details.json` (merges event dates, video URLs, Yoast SEO)
7. Create roundtable-tag associations
8. Populate roundtable-participant join table from `roundtable_participants.json`
9. Seed SiteConfig key-value pairs
10. Populate FTS5 search index

Expected seed time: under 10 seconds for the full dataset.

### 10.3 Production Deployment

**Server stack:**

- Ubuntu VPS (recommended: 2 vCPU, 2 GB RAM minimum)
- Node.js 18+ LTS
- PM2 process manager
- Nginx reverse proxy
- Let's Encrypt SSL via Certbot

**PM2 configuration (`ecosystem.config.js`):**

```javascript
module.exports = {
  apps: [{
    name: 'helixcenter',
    script: 'node_modules/.bin/next',
    args: 'start',
    cwd: '/var/www/helixcenter',
    env: {
      NODE_ENV: 'production',
      PORT: 3000,
    },
    instances: 1,
    autorestart: true,
    max_memory_restart: '512M',
  }],
};
```

**Nginx configuration (summary):**

```nginx
server {
    listen 443 ssl http2;
    server_name helixcenter.org www.helixcenter.org;

    ssl_certificate     /etc/letsencrypt/live/helixcenter.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/helixcenter.org/privkey.pem;

    # Cache static assets aggressively
    location /_next/static/ {
        expires 365d;
        add_header Cache-Control "public, immutable";
    }

    # Proxy to Next.js
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
```

### 10.4 Deployment Workflow

1. SSH into VPS
2. Pull latest code from repository
3. Run build steps (10.1)
4. `pm2 restart helixcenter`
5. Verify via health check

For automated deployments, a GitHub Actions workflow or similar CI/CD pipeline can execute these steps on push to `main`.

---

## 11. Performance

### 11.1 Targets

| Metric                     | Target    | Strategy                                |
|----------------------------|-----------|-----------------------------------------|
| First Contentful Paint     | < 2s      | Static HTML served from Nginx cache     |
| Largest Contentful Paint   | < 2.5s    | Optimized images, minimal JS            |
| Time to Interactive        | < 3s      | Server components reduce client JS      |
| Cumulative Layout Shift    | < 0.1     | Explicit image dimensions, font loading |
| SQLite query latency       | < 50ms    | Indexed queries, FTS5 for search        |
| Audio start (TTFB)         | < 1s      | External CDN streaming                  |

### 11.2 Optimization Strategies

**Static Assets:**
- Next.js generates hashed filenames for cache busting
- Nginx serves `/_next/static/` with 1-year cache headers and `immutable` directive
- Pre-rendered HTML pages are served directly without Node.js processing for cached routes

**Images:**
- Next.js `<Image>` component for automatic format optimization (WebP/AVIF), responsive sizing, and lazy loading
- Participant headshots served with explicit `width` and `height` to prevent layout shift
- Consider using `next/image` with the external media domain configured in `next.config.js`

**JavaScript:**
- Server components (default) ship zero client JS
- Client components (`"use client"`) used only for AudioPlayer, SearchBar, AlphabetFilter, and Pagination
- Code splitting via Next.js App Router automatically isolates per-route bundles

**Database:**
- SQLite queries execute in-process (no network round-trip)
- Prisma generates optimized SQL with proper indexes
- FTS5 queries use the built-in ranking function for relevance ordering
- Connection pooling is unnecessary -- SQLite uses file-level locking

### 11.3 Monitoring

- PM2 provides process-level CPU and memory monitoring (`pm2 monit`)
- Nginx access logs for request-level metrics
- Consider Lighthouse CI in the build pipeline for automated performance regression detection

---

## 12. Security Considerations

### 12.1 Input Validation

- **Search API:** Query parameter `q` is validated for minimum length (2 characters) and maximum length (200 characters). Parameterized queries via Prisma prevent SQL injection. FTS5 query syntax characters are escaped.
- **Contact form:** If implemented as a server action or API route, all inputs are validated and sanitized before processing.
- **Slug parameters:** Dynamic route slugs are validated against the database; unknown slugs return 404.

### 12.2 Content Security

- **WordPress HTML rendering:** Content from WordPress is rendered via `dangerouslySetInnerHTML`. A server-side sanitization pass (e.g., DOMPurify with jsdom) strips potentially dangerous elements (`<script>`, event handlers) before storage in the database or at render time. YouTube video embeds use a dedicated `VideoEmbed` component with an allowlisted `youtube.com/embed/` source rather than rendering raw `<iframe>` tags from WordPress content.
- **External links:** All external links in rendered WordPress content should include `rel="noopener noreferrer"` and optionally `target="_blank"`.

### 12.3 Transport Security

- **SSL/TLS:** All traffic to helixcenter.org is encrypted via Let's Encrypt certificates with automatic renewal via Certbot
- **HTTP to HTTPS redirect:** Nginx redirects all HTTP (port 80) requests to HTTPS (port 443)
- **HSTS:** `Strict-Transport-Security` header with a minimum `max-age` of 31536000 (1 year)
- **Audio URLs:** Note that audio files at `media.helixcenter.org` are currently served over HTTP. Consider upgrading to HTTPS or proxying through the main domain if mixed-content warnings arise.

### 12.4 HTTP Headers

Nginx should set the following security headers:

```nginx
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' https://www.helixcenter.org https://media.helixcenter.org data:; media-src 'self' http://media.helixcenter.org https://media.helixcenter.org; frame-src https://www.youtube.com; font-src 'self' data:;" always;
```

### 12.5 Database Security

- SQLite database file permissions should be restricted to the application user (`chmod 640`)
- The database file is not served by Nginx (located outside the `public/` directory)
- No remote database access -- SQLite is accessed exclusively in-process
- Prisma parameterized queries prevent SQL injection in all database operations

### 12.6 Environment & Secrets

- `.env` file is excluded from version control via `.gitignore`
- No API keys or authentication tokens are required for the public-facing site
- Server-only environment variables (e.g., `DATABASE_URL`) are never exposed to the client bundle
- PM2 environment variables are defined in `ecosystem.config.js`, which should have restricted file permissions on the server

### 12.7 Dependency Management

- Regular `npm audit` runs to identify and patch vulnerable dependencies
- Lock file (`package-lock.json`) committed to version control for reproducible builds
- Dependabot or similar automated dependency updates recommended

---

## Appendix A: Technology Decisions Summary

| Decision                          | Rationale                                                       |
|-----------------------------------|-----------------------------------------------------------------|
| Next.js 14 App Router             | Modern React with server components, built-in SSG, API routes   |
| SQLite over PostgreSQL             | Zero-ops, single-file database sufficient for read-heavy archival site |
| FTS5 over Algolia/Elasticsearch   | No external dependencies, sub-50ms queries for ~650 documents   |
| Tailwind CSS over CSS Modules     | Rapid prototyping, consistent design system, small CSS bundle   |
| PM2 over Docker                   | Simpler operational model for single-VPS deployment             |
| External audio hosting            | Avoid migrating large media files; existing CDN is reliable     |

## Appendix B: Related Documents

- [database-schema.md](database-schema.md) -- Complete Prisma schema with field definitions, indexes, and constraints
- [component-inventory.md](component-inventory.md) -- Full component hierarchy, props interfaces, and Tailwind styling patterns
