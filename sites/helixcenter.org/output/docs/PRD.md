# Product Requirements Document: Helix Center Website

**Project:** Helix Center Website Rebuild
**Domain:** helixcenter.org
**Version:** 1.0
**Date:** 2026-02-27
**Status:** Draft

---

## Table of Contents

1. [Overview](#1-overview)
2. [Mission and Brand](#2-mission-and-brand)
3. [Content Types and Data Model](#3-content-types-and-data-model)
4. [Content Relationships](#4-content-relationships)
5. [User Stories](#5-user-stories)
6. [Features](#6-features)
7. [Navigation and Information Architecture](#7-navigation-and-information-architecture)
8. [SEO and Structured Data](#8-seo-and-structured-data)
9. [Non-Functional Requirements](#9-non-functional-requirements)
10. [Success Metrics](#10-success-metrics)
11. [Out of Scope](#11-out-of-scope)
12. [Appendix: Content Inventory Summary](#appendix-content-inventory-summary)

---

## 1. Overview

### 1.1 Background

The Helix Center is a New York City-based non-profit organization that hosts interdisciplinary roundtable discussions bringing together experts across science, philosophy, the arts, and the humanities. The organization currently operates a WordPress website at helixcenter.org that serves as the primary public-facing platform for promoting events, archiving recorded roundtable discussions, and showcasing participants.

### 1.2 Purpose of This Document

This PRD defines the requirements for a complete rebuild of the Helix Center website. The rebuild will migrate from the existing WordPress installation to a modern, statically generated framework while preserving all content, relationships, and functionality. The new site must faithfully reproduce the information architecture, content types, and user-facing features of the existing site while improving performance, accessibility, and maintainability.

### 1.3 Scope

This document covers the full public-facing website including all content types, navigation, media handling, integrations, and non-functional requirements. It is informed by a comprehensive crawl and analysis of the existing WordPress site, including REST API data and rendered HTML scraping.

---

## 2. Mission and Brand

### 2.1 Mission Statement

**"An Unhurried Search for Wisdom"**

The Helix Center convenes scholars, scientists, artists, and thinkers for in-depth, interdisciplinary roundtable conversations. The website must reflect this mission through a design and experience that emphasizes intellectual depth, thoughtful exploration, and accessibility of ideas to a broad audience.

### 2.2 Brand Principles

- **Intellectual rigor**: Content presentation should foreground substance -- participant credentials, roundtable descriptions, and topic taxonomy.
- **Accessibility of ideas**: Video and audio recordings alongside detailed descriptions make complex discussions available to anyone.
- **Interdisciplinary connection**: The site should surface and encourage discovery of connections between roundtables, participants, and topics.
- **Unhurried experience**: The design should favor clarity and readability over visual noise. Navigation should feel deliberate, not overwhelming.

### 2.3 Target Audience

- Academics and researchers across disciplines
- Intellectually curious general public
- Potential donors and supporters
- Prospective roundtable participants and speakers
- Podcast listeners seeking long-form intellectual discussion
- Press and media

---

## 3. Content Types and Data Model

### 3.1 Roundtables (Custom Post Type)

The primary content type. Roundtables represent the core intellectual output of the Helix Center -- each is a recorded interdisciplinary discussion event.

**Total items:** 135

| Field | Description | Coverage |
|-------|-------------|----------|
| Title | Roundtable title/topic | 135/135 (100%) |
| Description/Content | Full narrative description of the roundtable discussion | 135/135 (100%) |
| Featured Image | Hero/banner image for the roundtable | 135/135 (100%) |
| Audio File | MP3 recording hosted at media.helixcenter.org | 127/135 (94%) |
| YouTube Video Embed | Embedded YouTube video of the roundtable recording | 127/135 (94%) |
| Event Date/Time | Human-readable event date and time (e.g., "October 4th, 2025 at 2:00PM") | 135/135 (100%) |
| Event Status | "Past Event" or "Future Event" indicator | 135/135 (100%) |
| Duration | Length of the audio recording | 127/135 (94%) |
| File Size | Size of the MP3 file | 127/135 (94%) |
| Date Recorded | Date the roundtable took place | 127/135 (94%) |
| Episode Type | Classification of the episode | 127/135 (94%) |
| Cover Image | Podcast-specific cover art | 127/135 (94%) |
| Series | Hierarchical taxonomy grouping related roundtables | 127/135 (94%) |
| Topic Tags | Thematic tags (e.g., "empathy", "neuroscience") | 126/135 (93%) |
| Participants | Linked participant profiles (many-to-many) | 125/135 (93%) |

**Key notes:**
- Roundtables serve dual duty as both event records and podcast episodes. The audio files hosted at media.helixcenter.org ARE the podcast content.
- 127 of 135 roundtables (94%) have embedded YouTube videos. The site's recorded content is primarily video, not audio-only. YouTube embed URLs were scraped from rendered roundtable HTML pages.
- Each roundtable has a human-readable event date/time and a status field ("Past Event" or "Future Event"), supporting an upcoming events feature on the site.
- Average of 5.5 participants per roundtable, reflecting the interdisciplinary panel format.
- The 8 roundtables without audio/video likely represent upcoming or recently announced events that have not yet occurred.

### 3.2 Participants (Custom Post Type)

Profiles of scholars, scientists, artists, and other experts who have participated in roundtable discussions.

**Total items:** 519

| Field | Description | Coverage |
|-------|-------------|----------|
| Name (Title) | Participant's full name | 519/519 (100%) |
| Professional Title/Affiliation | Title and institutional affiliation (e.g., "Professor of History, Yale University") | 452/519 (87%) |
| Biography/Content | Biographical description and credentials | 515/519 (99%) |
| Featured Image | Headshot photograph | 516/519 (99%) |
| Roundtable Links | Relationships to roundtable appearances | 510/519 (98%) |
| Papers/Presentations | Links to academic papers or presentations | 43/519 (8%) |

**Key notes:**
- Average of 1.4 roundtables per participant. Most participants appear in one roundtable, while a smaller number are recurring contributors.
- 452 of 519 participants (87%) have professional titles and institutional affiliations. These were scraped from individual participant HTML pages, as this data is not exposed via the WordPress REST API.
- 43 participants have papers/presentations sections, also scraped from rendered HTML.
- The participant-roundtable relationship is managed via ACF (Advanced Custom Fields) or custom meta, not through the WordPress REST API natively. Relationship data was extracted from rendered HTML.

### 3.3 Pages (Standard WordPress Pages)

Static content pages providing organizational information.

**Total items:** 19

**Top-level pages:**
- Home
- About
- Community
- Videos
- Roundtable Archive
- Participant Archive
- Contact
- Donate
- Mailing List
- Board of Advisors

**Child pages (under About):**
- Board of Directors
- Executive Committee
- Arts/Humanities
- Music
- Film
- Digital

### 3.4 Podcasts (Legacy Custom Post Type)

**Total items:** 9

A legacy content type that is largely redundant. The roundtable CPT already contains all podcast-relevant fields (audio file, duration, file size, episode type, cover image). These 9 items should be evaluated during migration to determine if they contain any unique content not already captured in the roundtable records. If not, they can be safely deprecated.

### 3.5 Taxonomies

#### 3.5.1 Topic Tags
- **Total:** 513 unique tags
- Applied to roundtables for thematic categorization
- Examples: "empathy", "neuroscience", "consciousness", "aesthetics", "ethics"
- Enable topic-based discovery and filtering of roundtables

#### 3.5.2 Series
- **Total:** 1 series ("The Helix Center") with a full description
- Hierarchical taxonomy for grouping roundtables into a podcast series
- Applied to 127 roundtables (94% coverage)
- Serves as the podcast series grouping for RSS/podcast distribution
- Enables browsing roundtables by series

### 3.6 Media Library

- **Total:** 98 items in the WordPress media library
- Primarily images (featured images for roundtables and participant headshots)
- Audio files are hosted externally at media.helixcenter.org, not in the WordPress media library

---

## 4. Content Relationships

### 4.1 Roundtable-Participant Relationship

**Type:** Many-to-many
**Implementation in source:** ACF / custom meta fields, rendered by the WordPress theme
**Discovery method:** Scraped from rendered HTML (not available via REST API)

| Metric | Value |
|--------|-------|
| Roundtables with participant data | 125 of 135 (93%) |
| Total relationship links | 690 |
| Average participants per roundtable | 5.5 |
| Average roundtables per participant | 1.4 |

**Requirements for rebuild:**
- Each roundtable detail page must list all associated participants with links to their profiles.
- Each participant detail page must list all roundtables they have appeared in with links to those roundtable pages.
- The relationship data must be stored in a structured, queryable format (e.g., a join table, frontmatter references, or a relational data layer).

### 4.2 Roundtable-Series Relationship

**Type:** Many-to-one (each roundtable belongs to one series)
**Coverage:** 127 of 135 roundtables (94%)

### 4.3 Roundtable-Tag Relationship

**Type:** Many-to-many
**Coverage:** 126 of 135 roundtables (93%)
**Tag count:** 513 unique tags

### 4.4 Page Hierarchy

**Type:** Parent-child
About page serves as parent for Board of Directors, Executive Committee, Arts/Humanities, Music, Film, and Digital sub-pages.

---

## 5. User Stories

### 5.1 Roundtable Discovery and Consumption

| ID | Story | Priority |
|----|-------|----------|
| US-01 | As a visitor, I want to browse a chronological list of upcoming and past roundtables so that I can find discussions that interest me. | P0 |
| US-02 | As a visitor, I want to watch video recordings of past roundtables directly on the website so that I can engage with the content without leaving the site. | P0 |
| US-02a | As a visitor, I want to listen to audio recordings of past roundtables so that I can engage with the content in audio-only format (e.g., while commuting). | P0 |
| US-02b | As a visitor, I want to see which roundtables are upcoming ("Future Event") so that I can plan to attend or watch for new recordings. | P1 |
| US-03 | As a visitor, I want to view a roundtable's full description, date, participants, and topic tags so that I can understand what was discussed. | P0 |
| US-04 | As a visitor, I want to filter or browse roundtables by topic tag so that I can find discussions on subjects I care about. | P1 |
| US-05 | As a visitor, I want to browse roundtables by series so that I can follow a curated sequence of related discussions. | P1 |

### 5.2 Participant Discovery

| ID | Story | Priority |
|----|-------|----------|
| US-06 | As a visitor, I want to browse participants alphabetically using A-Z letter navigation so that I can quickly find a specific person. | P0 |
| US-07 | As a visitor, I want to view a participant's biography, professional title/affiliation, and headshot so that I can learn about their background and credentials. | P0 |
| US-07a | As a visitor, I want to see a participant's papers and presentations (when available) so that I can explore their academic work. | P1 |
| US-08 | As a visitor, I want to see all roundtables a participant has appeared in so that I can explore their contributions. | P0 |

### 5.3 Organizational Information

| ID | Story | Priority |
|----|-------|----------|
| US-09 | As a visitor, I want to read about the Helix Center's mission and organizational structure so that I understand what the organization does. | P0 |
| US-10 | As a visitor, I want to navigate the About page hierarchy (board of directors, executive committee, arts programs) so that I can learn about leadership and programs. | P0 |

### 5.4 Engagement and Communication

| ID | Story | Priority |
|----|-------|----------|
| US-11 | As a visitor, I want to contact the Helix Center via a contact form so that I can ask questions or make inquiries. | P0 |
| US-12 | As a supporter, I want to donate to the Helix Center so that I can financially support their mission. | P0 |
| US-13 | As a visitor, I want to subscribe to the mailing list or newsletter so that I receive updates about new roundtables and events. | P1 |
| US-14 | As a podcast listener, I want to access an RSS feed so that I can subscribe in my podcast app of choice. | P1 |
| US-15 | As a visitor, I want to find and follow the Helix Center on social media so that I can stay connected. | P2 |

---

## 6. Features

### 6.1 Video Player (YouTube Embed)

**Priority:** P0

Embedded YouTube video player for roundtable recordings. 127 of 135 roundtables have YouTube video embeds.

**Requirements:**
- Responsive YouTube iframe embed on roundtable detail pages
- Privacy-enhanced mode (youtube-nocookie.com) where feasible
- Lazy-load video embeds to minimize impact on page load performance
- Fallback message for the 8 roundtables without video (upcoming events)
- Accessible: keyboard navigable, screen reader compatible
- Mobile-friendly: responsive embed that scales to viewport width

### 6.1a Audio Player

**Priority:** P0

An embedded audio player for roundtable MP3 recordings, providing an alternative to video playback.

**Requirements:**
- Play/pause, seek, and volume controls
- Display current time and total duration
- Stream MP3 files from media.helixcenter.org
- Persistent playback: audio should continue playing when navigating between pages (consider a fixed/floating player)
- Accessible: keyboard navigable, screen reader compatible
- Mobile-friendly: responsive controls, works on iOS/Android browsers
- Display roundtable title and cover image during playback

### 6.2 Roundtable Archive

**Priority:** P0

A browsable, paginated listing of all roundtables.

**Requirements:**
- Display roundtable title, featured image, date, and brief excerpt
- Distinguish between upcoming and past events using the scraped event status field ("Past Event" / "Future Event")
- Display human-readable event date/time (e.g., "October 4th, 2025 at 2:00PM")
- Sort by date (newest first by default)
- Optional filter or section for upcoming ("Future Event") roundtables to support event discovery
- Pagination or infinite scroll for the full archive
- Each item links to the full roundtable detail page

### 6.3 Roundtable Detail Page

**Priority:** P0

Individual page for each roundtable.

**Requirements:**
- Full description/content
- Featured image
- Human-readable event date/time and event status ("Past Event" / "Future Event") with visual indicator
- Embedded YouTube video player (if video embed exists -- 127/135 roundtables)
- Embedded audio player (if audio file exists)
- List of participants with headshots, names, and links to participant profiles
- Topic tags displayed as clickable links
- Series affiliation displayed with link to series archive

### 6.4 Participant Archive

**Priority:** P0

Alphabetical listing of all 519 participants.

**Requirements:**
- A-Z letter navigation allowing users to jump to participants by first letter of last name
- Display headshot thumbnail, name, and professional title/affiliation (when available) for each participant
- Each item links to the full participant detail page
- Responsive grid layout

### 6.5 Participant Detail Page

**Priority:** P0

Individual page for each participant.

**Requirements:**
- Professional title and institutional affiliation (when available -- 452/519 participants)
- Full biography/content
- Featured image (headshot)
- Papers and presentations section (when available -- 43/519 participants)
- List of all roundtables the participant has appeared in, with links
- Roundtable list should include title, date, and featured image thumbnail

### 6.6 Contact Form

**Priority:** P0

**Requirements:**
- Standard contact form fields (name, email, subject, message)
- Server-side validation and spam protection (honeypot or CAPTCHA)
- Confirmation message on successful submission
- Email delivery to designated Helix Center address

### 6.7 Donate Page/Button

**Priority:** P0

**Requirements:**
- Prominent donate call-to-action in navigation
- Dedicated donate page with clear instructions
- Integration with payment processor (to be determined -- existing provider or new)
- Secure, PCI-compliant payment handling

### 6.8 Newsletter/Mailing List Signup

**Priority:** P1

**Requirements:**
- Email signup form (Mailchimp integration, matching existing setup)
- Can be embedded on dedicated mailing list page and optionally in footer or sidebar
- Double opt-in confirmation
- GDPR-compliant data handling

### 6.9 RSS Feed

**Priority:** P1

**Requirements:**
- Valid RSS 2.0 or Atom feed for roundtables
- Include enclosure tags for audio files to support podcast client subscription
- Include title, description, date, duration, and audio URL per item
- iTunes/Apple Podcasts compatible tags (itunes:duration, itunes:image, etc.)
- Feed URL should be discoverable via `<link rel="alternate">` in HTML head

### 6.10 Topic Tag Archive Pages

**Priority:** P1

**Requirements:**
- Each of the 513 topic tags should have an archive page listing all roundtables with that tag
- Tag cloud or tag listing page for discovery
- Tags displayed as clickable links on roundtable detail pages

### 6.11 Series Archive Pages

**Priority:** P1

**Requirements:**
- Each series should have an archive page listing all roundtables in that series
- Series listing page for discovery

### 6.12 Social Media Links

**Priority:** P2

**Requirements:**
- Links to Facebook, Twitter/X, YouTube, Instagram, Apple Podcasts in footer
- RSS feed link in footer
- "View Map" link (Google Maps or embedded map showing NYC location)

---

## 7. Navigation and Information Architecture

### 7.1 Primary Navigation (Header)

```
Roundtables    Participants    About (dropdown)    Contact    Donate
                                 |-- About
                                 |-- Board of Directors
                                 |-- Executive Committee
```

**Requirements:**
- Sticky/fixed header on scroll (if matching existing behavior)
- Mobile: hamburger menu or equivalent responsive navigation
- "Donate" should be visually distinct (button style) to encourage engagement
- About dropdown should expand on hover (desktop) and tap (mobile)

### 7.2 Footer Navigation

- Social media links: Facebook, Twitter/X, YouTube, Instagram, Apple Podcasts
- RSS feed link
- View Map link (location)
- Copyright notice

### 7.3 URL Structure

Preserve existing URL patterns for SEO continuity and to avoid broken links:

| Content Type | URL Pattern |
|-------------|-------------|
| Roundtable archive | `/roundtable/` |
| Roundtable detail | `/roundtable/{slug}/` |
| Participant archive | `/participant/` |
| Participant detail | `/participant/{slug}/` |
| Page | `/{slug}/` |
| About child pages | `/about/{slug}/` |
| Topic tag archive | `/tag/{slug}/` |
| Series archive | `/series/{slug}/` |

**Requirements:**
- All existing URLs must either continue to work or have 301 redirects to new URLs.
- Trailing slash behavior should be consistent.

---

## 8. SEO and Structured Data

### 8.1 On-Page SEO

The existing site uses Yoast SEO, which provides og:description, og:image, and canonical URLs for all roundtables and participants. These existing SEO metadata values should be preserved during migration to maintain SEO continuity and social sharing quality.

**Requirements:**
- Unique, descriptive `<title>` tags for every page (pattern: `{Page Title} | The Helix Center`)
- Meta description tags for all pages, roundtables, and participants (preserve existing Yoast SEO descriptions)
- Canonical URLs on every page (`<link rel="canonical">`) -- preserve existing canonical URLs from Yoast SEO
- Open Graph tags (og:title, og:description, og:image, og:url, og:type) for social sharing -- preserve existing Yoast og:description and og:image values
- Twitter Card tags (twitter:card, twitter:title, twitter:description, twitter:image)

### 8.2 Structured Data (JSON-LD)

| Content Type | Schema.org Type | Key Properties |
|-------------|----------------|----------------|
| Roundtable | `Event` | name, description, startDate, location, performer, image, video (YouTube embed URL), audio (if available) |
| Participant | `Person` | name, description, image, url, jobTitle, affiliation (when available) |
| Organization (site-wide) | `Organization` | name, url, logo, sameAs (social links) |

**Requirements:**
- JSON-LD scripts embedded in `<head>` or `<body>` of relevant pages
- Valid per Google's Rich Results testing tool
- Event schema should include `eventStatus` (scheduled, completed) and `eventAttendanceMode`

### 8.3 Technical SEO

**Requirements:**
- XML sitemap covering all roundtables, participants, pages, tag archives, and series archives
- `robots.txt` with appropriate directives
- Clean, semantic HTML5 structure with proper heading hierarchy (single `<h1>` per page)
- Image alt text on all images
- Internal linking between related content (roundtable-participant cross-links)
- Page speed optimization (see Non-Functional Requirements)

---

## 9. Non-Functional Requirements

### 9.1 Performance

| Metric | Target |
|--------|--------|
| First Contentful Paint (FCP) | < 2.0 seconds |
| Largest Contentful Paint (LCP) | < 2.5 seconds |
| Cumulative Layout Shift (CLS) | < 0.1 |
| Time to Interactive (TTI) | < 3.5 seconds |
| Lighthouse Performance Score | >= 90 |

**Requirements:**
- Static site generation (SSG) for all content pages where possible
- Image optimization: WebP/AVIF format, responsive srcset, lazy loading
- CSS and JavaScript minification and bundling
- CDN deployment for static assets
- Efficient font loading (font-display: swap, subset if using custom fonts)

### 9.2 Accessibility

**Standard:** WCAG 2.1 Level AA

**Requirements:**
- Keyboard navigation for all interactive elements
- Screen reader compatibility (ARIA labels, roles, live regions for audio player)
- Sufficient color contrast ratios (minimum 4.5:1 for normal text, 3:1 for large text)
- Focus indicators on all interactive elements
- Alt text on all images
- Audio player accessible via keyboard and assistive technology
- Skip navigation link
- Semantic HTML structure
- Forms with proper labels and error messaging

### 9.3 Responsiveness

**Requirements:**
- Fully responsive design across breakpoints:
  - Mobile: 320px - 767px
  - Tablet: 768px - 1023px
  - Desktop: 1024px+
- Touch-friendly tap targets (minimum 44x44px)
- Readable text without zooming on mobile
- Images scale appropriately across screen sizes
- Navigation adapts to mobile (hamburger menu or equivalent)

### 9.4 Browser Support

| Browser | Minimum Version |
|---------|----------------|
| Chrome | Last 2 major versions |
| Firefox | Last 2 major versions |
| Safari | Last 2 major versions |
| Edge | Last 2 major versions |
| iOS Safari | Last 2 major versions |
| Chrome for Android | Last 2 major versions |

### 9.5 Hosting and Infrastructure

**Requirements:**
- Static hosting with CDN (e.g., Vercel, Netlify, Cloudflare Pages)
- HTTPS with valid TLS certificate
- Custom domain: helixcenter.org (and www.helixcenter.org redirect)
- Automated builds triggered by content changes
- 99.9% uptime target

### 9.6 Content Management

**Requirements:**
- Headless CMS or markdown-based content management for non-technical editors
- Preview capability before publishing
- Draft/publish workflow
- Media upload and management
- Ability to add new roundtables, participants, and pages without developer intervention

### 9.7 Security

**Requirements:**
- No server-side code exposed to the public (static generation mitigates most attack vectors)
- Form submissions processed via serverless functions or third-party service
- CSRF protection on all forms
- Content Security Policy headers
- Rate limiting on form endpoints to prevent abuse

---

## 10. Success Metrics

### 10.1 Migration Completeness

| Metric | Target |
|--------|--------|
| Roundtables migrated | 135/135 (100%) |
| Participants migrated | 519/519 (100%) |
| Participant professional titles preserved | 452/452 (100% of those with titles) |
| Participant papers/presentations preserved | 43/43 (100% of those with papers) |
| Pages migrated | 19/19 (100%) |
| Roundtable-participant relationships preserved | 690/690 (100%) |
| YouTube video embeds preserved | 127/127 (100%) |
| Audio files accessible | 127/127 (100%) |
| Event date/time and status preserved | 135/135 (100%) |
| SEO metadata preserved (og:description, og:image, canonical) | 100% of roundtables and participants |
| Featured images migrated | All with source coverage |
| URL parity or redirects | 100% of existing URLs resolve |

### 10.2 Performance

| Metric | Target |
|--------|--------|
| Lighthouse Performance | >= 90 |
| Lighthouse Accessibility | >= 95 |
| Lighthouse SEO | >= 95 |
| Lighthouse Best Practices | >= 90 |
| FCP | < 2.0s |

### 10.3 SEO Continuity

| Metric | Target |
|--------|--------|
| Indexed pages (post-migration) | No decrease from current |
| Organic search traffic (30 days post-launch) | No decrease vs. pre-migration baseline |
| Broken links / 404 errors | 0 (all redirected) |

### 10.4 User Engagement

| Metric | Measurement Method |
|--------|-------------------|
| Video plays per session | YouTube embed analytics / event tracking |
| Audio plays per session | Analytics event tracking |
| Pages per session | Analytics |
| Average session duration | Analytics |
| Newsletter signups | Mailchimp reporting |
| Contact form submissions | Form service reporting |

---

## 11. Out of Scope

The following items are explicitly excluded from this project:

1. **User authentication / member accounts**: The site is fully public. No login, registration, or gated content.
2. **E-commerce**: Beyond the donate button/page, no shopping cart, product catalog, or transactional commerce.
3. **Live streaming**: The site archives recorded roundtables. Live event streaming is not in scope.
4. **Self-hosted video**: Video content is hosted on YouTube and embedded via iframe. 127 of 135 roundtables have YouTube video embeds. The site will embed YouTube videos, not host video files directly. YouTube embed support is in scope (see Feature 6.1); self-hosted video infrastructure is not.
5. **Blog / news section**: The site does not have an active blog. If blog content is needed in the future, it can be added as a separate phase.
6. **Multi-language / internationalization**: English only.
7. **Advanced search**: Full-text search across all content types. A basic tag/series browsing interface is in scope; Elasticsearch-style search is not.
8. **WordPress admin panel recreation**: The CMS backend will be a modern headless CMS or file-based system, not a WordPress replica.
9. **Legacy podcast CPT migration**: The 9 legacy podcast items will be evaluated for unique content. If they contain no content beyond what exists in the roundtable CPT, they will not be migrated as a separate content type.
10. **Comment system**: The existing site does not appear to use comments. No comment functionality will be built.
11. **Custom analytics dashboard**: Standard analytics integration (Google Analytics or equivalent) is in scope; a custom reporting dashboard is not.

---

## Appendix: Content Inventory Summary

| Content Type | Count | Key Coverage Notes |
|-------------|-------|--------------------|
| Roundtables | 135 | 94% have audio, 94% have YouTube video embeds, 93% have participant links |
| Participants | 519 | 99% have bios, 99% have headshots, 87% have professional titles |
| Participant Papers/Presentations | 43 | 8% of participants have papers/presentations sections |
| Pages | 19 | 6 under About hierarchy |
| Podcasts (legacy) | 9 | Likely redundant with roundtable audio |
| Topic Tags | 513 | Applied to 93% of roundtables |
| Series | 1 ("The Helix Center") | Applied to 94% of roundtables; full description available |
| Media Library Items | 98 | Images (audio hosted externally) |
| Roundtable-Participant Links | 690 | Avg 5.5 participants per roundtable |

### Data Source Notes

Content was gathered from two complementary sources:

**WordPress REST API** (structured data):
- `wp_posts.json` -- roundtable content, descriptions, and podcast meta fields
- `wp_participants.json` -- participant names, biographies, and featured images
- `wp_pages.json` -- static page content and hierarchy
- `wp_tags.json` -- 513 topic tags
- `wp_media.json` -- media library items (98 images)
- `wp_series.json` -- series taxonomy (1 series with full description)

**HTML scraping** (data not exposed via API):
- `roundtable_details.json` -- YouTube video embed URLs, event date/time, event status ("Past Event" / "Future Event"), and Yoast SEO metadata (og:description, og:image, canonical URLs)
- `roundtable_participants.json` -- roundtable-to-participant relationship links (690 links)
- `participant_titles.json` -- professional titles/affiliations (452/519 participants) and papers/presentations sections (43 participants), scraped from individual participant HTML pages; also includes Yoast SEO metadata

Audio files are hosted on a separate subdomain (media.helixcenter.org) and are referenced by URL in the roundtable meta fields. Video content is hosted on YouTube and referenced by embed URL in the scraped roundtable data.
