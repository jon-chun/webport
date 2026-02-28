# Database Schema: Helix Center

## Overview

This document defines the database schema for the Helix Center website migration. The schema models the WordPress content types -- roundtables, participants, tags, series, pages, and media -- as a normalized relational database using Prisma ORM with an SQLite provider.

The source data originates from the WordPress REST API and supplemental HTML scraping. All WordPress IDs are preserved as `wpId` fields to maintain traceability back to the source CMS, while Prisma manages its own autoincrement primary keys where appropriate.

### Design Principles

1. **Preserve WordPress IDs** -- Every content type retains its original `wpId` for cross-referencing during seed and future audits.
2. **Normalize relationships** -- Many-to-many relationships (roundtable-participant, roundtable-tag) use explicit join tables with composite unique constraints.
3. **HTML content stored as-is** -- Rendered HTML from `content.rendered` and `excerpt.rendered` is stored verbatim. Transformation to JSX/MDX happens at the presentation layer.
4. **Self-referential hierarchy** -- Pages support parent-child relationships via a nullable `parentId` foreign key.
5. **SQLite for portability** -- The dev/build database uses SQLite for zero-configuration local development. Production can swap to PostgreSQL by changing the provider.

---

## Data Stats

| Model                  | Count | Notes                              |
|------------------------|------:|------------------------------------|
| Roundtable             |   135 | 127 with audio files               |
| Participant            |   519 | 516 with featured images           |
| RoundtableParticipant  |   690 | Join records (scraped from HTML)    |
| Tag                    |   513 |                                    |
| Page                   |    19 | Hierarchical (parent-child)        |
| Media                  |    98 |                                    |
| Series                 |   var | Extracted from roundtable metadata |
| SiteConfig             |   var | Key-value site settings            |

---

## Prisma Schema

```prisma
// prisma/schema.prisma

generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "sqlite"
  url      = env("DATABASE_URL") // e.g. "file:./dev.db"
}

// ---------------------------------------------------------------------------
// Roundtable
// ---------------------------------------------------------------------------
// Source: wp_posts.json (post_type: "roundtable")
// WordPress REST API endpoint: /wp-json/wp/v2/roundtable
// ---------------------------------------------------------------------------
model Roundtable {
  id               Int       @id @default(autoincrement())
  wpId             Int       @unique
  slug             String    @unique
  title            String    // title.rendered
  content          String    // content.rendered (HTML)
  excerpt          String    @default("") // excerpt.rendered (HTML)
  publishedAt      DateTime  // date (ISO 8601)
  updatedAt        DateTime  // modified (ISO 8601)
  dateRecorded     DateTime? // meta.date_recorded
  eventDatetime    String?   // "October 4th, 2025 at 2:00PM" (scraped from HTML)
  eventStatus      String?   // "Past Event" or "Future Event"
  audioFile        String?   // meta.audio_file (URL)
  audioDuration    String?   // meta.duration (e.g. "1:23:45")
  audioFilesize    String?   // meta.filesize (e.g. "45000000")
  audioFilesizeRaw String?   // Raw bytes as string
  episodeType      String?   // meta.episode_type (e.g. "full")
  videoUrl         String?   // YouTube embed URL (scraped from HTML)
  downloadLink     String?   // Podcast download URL
  playerLink       String?   // Podcast player URL
  ogDescription    String?   // Yoast OG description
  ogImageUrl       String?   // Yoast OG image URL
  canonicalUrl     String?   // Yoast canonical URL
  featuredMediaId  Int?      // featured_media (WP media ID)
  sourceUrl        String    // link (original WordPress URL)
  status           String    @default("publish") // status

  // Relations
  participants    RoundtableParticipant[]
  tags            RoundtableTag[]
  series          Series?   @relation(fields: [seriesId], references: [wpId])
  seriesId        Int?
  featuredImage   Media?    @relation(fields: [featuredMediaId], references: [wpId])

  @@index([slug])
  @@index([publishedAt])
  @@index([status])
}

// ---------------------------------------------------------------------------
// Participant
// ---------------------------------------------------------------------------
// Source: wp_participants.json (post_type: "participant")
// WordPress REST API endpoint: /wp-json/wp/v2/participant
// ---------------------------------------------------------------------------
model Participant {
  id                Int     @id @default(autoincrement())
  wpId              Int     @unique
  slug              String  @unique
  name              String  // title.rendered
  professionalTitle String  @default("")  // "Professor, Neuroscience, Icahn School of Medicine"
  bio               String  @default("")  // Full HTML biography (content.rendered)
  hasPapers         Boolean @default(false) // Has papers/presentations section
  papersText        String  @default("")  // Papers/presentations content
  ogDescription     String  @default("")  // Yoast OG description (truncated bio)
  ogImageUrl        String  @default("")  // Yoast OG image URL
  featuredMediaId   Int?    // featured_media (WP media ID)
  sourceUrl         String  // link (original WordPress URL)

  // Relations
  roundtables     RoundtableParticipant[]
  featuredImage   Media?    @relation(fields: [featuredMediaId], references: [wpId])

  @@index([slug])
  @@index([name])
}

// ---------------------------------------------------------------------------
// RoundtableParticipant (join table)
// ---------------------------------------------------------------------------
// Source: roundtable_participants.json (scraped from HTML)
// Maps roundtable slugs to participant slugs
// ---------------------------------------------------------------------------
model RoundtableParticipant {
  id            Int          @id @default(autoincrement())
  roundtableId  Int
  participantId Int

  roundtable    Roundtable   @relation(fields: [roundtableId], references: [id])
  participant   Participant  @relation(fields: [participantId], references: [id])

  @@unique([roundtableId, participantId])
  @@index([roundtableId])
  @@index([participantId])
}

// ---------------------------------------------------------------------------
// Tag
// ---------------------------------------------------------------------------
// Source: wp_tags.json
// WordPress REST API endpoint: /wp-json/wp/v2/tags
// ---------------------------------------------------------------------------
model Tag {
  id          Int             @id @default(autoincrement())
  wpId        Int             @unique
  slug        String          @unique
  name        String          // name

  // Relations
  roundtables RoundtableTag[]

  @@index([slug])
}

// ---------------------------------------------------------------------------
// RoundtableTag (join table)
// ---------------------------------------------------------------------------
// Populated by iterating roundtable.tags[] (array of WP tag IDs)
// ---------------------------------------------------------------------------
model RoundtableTag {
  id           Int        @id @default(autoincrement())
  roundtableId Int
  tagId        Int

  roundtable   Roundtable @relation(fields: [roundtableId], references: [id])
  tag          Tag        @relation(fields: [tagId], references: [id])

  @@unique([roundtableId, tagId])
  @@index([roundtableId])
  @@index([tagId])
}

// ---------------------------------------------------------------------------
// Series
// ---------------------------------------------------------------------------
// Source: wp_series.json or extracted from roundtable taxonomy
// WordPress REST API endpoint: /wp-json/wp/v2/series (custom taxonomy)
// ---------------------------------------------------------------------------
model Series {
  id          Int          @id @default(autoincrement())
  wpId        Int          @unique
  slug        String       @unique
  name        String       // name
  description String       @default("") // description

  // Relations
  roundtables Roundtable[]

  @@index([slug])
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
// Source: wp_pages.json
// WordPress REST API endpoint: /wp-json/wp/v2/pages
// Supports hierarchical parent-child relationships
// ---------------------------------------------------------------------------
model Page {
  id        Int     @id @default(autoincrement())
  wpId      Int     @unique
  slug      String  @unique
  title     String  // title.rendered
  content   String  // content.rendered (HTML)
  parentId  Int?    // parent (WP page ID, self-referential)
  menuOrder Int     @default(0) // menu_order
  sourceUrl String  // link (original WordPress URL)

  // Self-referential relations
  parent    Page?   @relation("PageHierarchy", fields: [parentId], references: [id])
  children  Page[]  @relation("PageHierarchy")

  @@index([slug])
  @@index([parentId])
}

// ---------------------------------------------------------------------------
// Media
// ---------------------------------------------------------------------------
// Source: wp_media.json
// WordPress REST API endpoint: /wp-json/wp/v2/media
// ---------------------------------------------------------------------------
model Media {
  id        Int     @id @default(autoincrement())
  wpId      Int     @unique
  sourceUrl String  // source_url (full-size image URL)
  title     String  @default("") // title.rendered
  altText   String  @default("") // alt_text
  caption   String  @default("") // caption.rendered
  mimeType  String  @default("") // mime_type (e.g. "image/jpeg")
  width     Int?    // media_details.width
  height    Int?    // media_details.height
  filesize  Int?    // Size in bytes
  // Image size variants stored as JSON string
  sizes     String  @default("{}") // JSON: {thumbnail: {url, w, h}, medium: {...}, ...}

  // Relations (inverse)
  roundtables  Roundtable[]
  participants Participant[]

  @@index([wpId])
}

// ---------------------------------------------------------------------------
// SiteConfig
// ---------------------------------------------------------------------------
// Key-value store for site-wide configuration
// Examples: site_title, site_description, primary_menu_json
// ---------------------------------------------------------------------------
model SiteConfig {
  id    Int    @id @default(autoincrement())
  key   String @unique
  value String
}
```

---

## ER Diagram

```
┌─────────────────────┐       ┌──────────────────────────────┐       ┌────────────────────────┐
│       Series        │       │         Roundtable           │       │        Media           │
├─────────────────────┤       ├──────────────────────────────┤       ├────────────────────────┤
│ id           (PK)   │       │ id                (PK)       │       │ id          (PK)       │
│ wpId         (UQ)   │◄──┐  │ wpId              (UQ)       │  ┌───►│ wpId        (UQ)       │
│ slug         (UQ)   │   │  │ slug              (UQ)       │  │    │ sourceUrl              │
│ name               │   │  │ title                        │  │    │ title                  │
│ description        │   │  │ content            (HTML)    │  │    │ altText                │
└─────────────────────┘   │  │ excerpt            (HTML)    │  │    │ caption                │
                          │  │ publishedAt                  │  │    │ mimeType               │
                          │  │ updatedAt                    │  │    │ width                  │
                          │  │ dateRecorded                 │  │    │ height                 │
                          │  │ eventDatetime                │  │    │ filesize               │
                          │  │ eventStatus                  │  │    │ sizes          (JSON)  │
                          │  │ audioFile                    │  │    └────────────────────────┘
                          │  │ audioDuration                │  │              ▲
                          │  │ audioFilesize                │  │              │
                          │  │ audioFilesizeRaw             │  │              │
                          │  │ episodeType                  │  │    ┌────────┴───────────┐
                          │  │ videoUrl                     │  │    │   (also referenced │
                          │  │ downloadLink                 │  │    │   by Participant)  │
                          │  │ playerLink                   │  │    └────────────────────┘
                          │  │ ogDescription                │  │
                          │  │ ogImageUrl                   │  │
                          │  │ canonicalUrl                 │  │
                          │  │ featuredMediaId       (FK)───┼──┘
                          └──┤ seriesId              (FK)   │
                             │ sourceUrl                    │
                             │ status                       │
                             └──────────┬──────┬────────────┘
                                        │      │
                           ┌────────────┘      └────────────┐
                           ▼                                ▼
           ┌──────────────────────────┐     ┌──────────────────────────┐
           │  RoundtableParticipant   │     │     RoundtableTag        │
           │       (join table)       │     │      (join table)        │
           ├──────────────────────────┤     ├──────────────────────────┤
           │ id              (PK)     │     │ id              (PK)     │
           │ roundtableId    (FK)     │     │ roundtableId    (FK)     │
           │ participantId   (FK)     │     │ tagId           (FK)     │
           │                          │     │                          │
           │ UQ(roundtableId,         │     │ UQ(roundtableId, tagId)  │
           │    participantId)        │     └─────────────┬────────────┘
           └──────────────┬───────────┘                   │
                          │                               ▼
                          ▼                  ┌────────────────────┐
           ┌──────────────────────────┐      │       Tag          │
           │     Participant          │      ├────────────────────┤
           ├──────────────────────────┤      │ id          (PK)   │
           │ id              (PK)     │      │ wpId        (UQ)   │
           │ wpId            (UQ)     │      │ slug        (UQ)   │
           │ slug            (UQ)     │      │ name               │
           │ name                     │      └────────────────────┘
           │ professionalTitle        │
           │ bio             (HTML)   │
           │ hasPapers       (Bool)   │
           │ papersText               │
           │ ogDescription            │
           │ ogImageUrl               │
           │ featuredMediaId (FK)─────┼──────────────► Media
           │ sourceUrl                │
           └──────────────────────────┘


           ┌──────────────────────────┐      ┌────────────────────┐
           │        Page              │      │    SiteConfig      │
           ├──────────────────────────┤      ├────────────────────┤
           │ id              (PK)     │      │ id          (PK)   │
           │ wpId            (UQ)     │      │ key         (UQ)   │
           │ slug            (UQ)     │      │ value              │
           │ title                    │      └────────────────────┘
           │ content         (HTML)   │
           │ parentId        (FK)─────┼──┐
           │ menuOrder                │  │
           │ sourceUrl                │  │
           └──────────────────────────┘  │
                     ▲                   │
                     └───────────────────┘
                     (self-referential: parent/children)
```

### Relationship Summary

| Relationship                     | Type        | Description                                         |
|----------------------------------|-------------|-----------------------------------------------------|
| Roundtable ↔ Participant         | Many-to-Many| Via `RoundtableParticipant` join table               |
| Roundtable ↔ Tag                 | Many-to-Many| Via `RoundtableTag` join table                       |
| Roundtable → Series              | Many-to-One | Each roundtable optionally belongs to one series     |
| Roundtable → Media               | Many-to-One | Featured image via `featuredMediaId` → `Media.wpId`  |
| Participant → Media              | Many-to-One | Featured image via `featuredMediaId` → `Media.wpId`  |
| Page → Page                      | Self-ref    | Parent-child hierarchy via `parentId`                |

---

## WordPress Field to Prisma Mapping Tables

### Roundtable Field Mapping

| WordPress REST API Field     | JSON Path                   | Prisma Field       | Type       | Notes                              |
|------------------------------|-----------------------------|--------------------|------------|------------------------------------|
| `id`                         | `id`                        | `wpId`             | `Int`      | Unique, not the Prisma PK          |
| `slug`                       | `slug`                      | `slug`             | `String`   | Unique                             |
| `title.rendered`             | `title.rendered`            | `title`            | `String`   | HTML entities decoded              |
| `content.rendered`           | `content.rendered`          | `content`          | `String`   | Raw HTML preserved                 |
| `excerpt.rendered`           | `excerpt.rendered`          | `excerpt`          | `String`   | Raw HTML preserved; default `""`   |
| `date`                       | `date`                      | `publishedAt`      | `DateTime` | ISO 8601 format                    |
| `modified`                   | `modified`                  | `updatedAt`        | `DateTime` | ISO 8601 format                    |
| `meta.date_recorded`         | `meta.date_recorded`        | `dateRecorded`     | `DateTime?`| May be empty string (treat as null)|
| *(scraped from HTML)*        | *(event datetime text)*     | `eventDatetime`    | `String?`  | e.g. "October 4th, 2025 at 2:00PM"|
| *(scraped from HTML)*        | *(event status badge)*      | `eventStatus`      | `String?`  | "Past Event" or "Future Event"     |
| `meta.audio_file`            | `meta.audio_file`           | `audioFile`        | `String?`  | Full URL to MP3/audio file         |
| `meta.duration`              | `meta.duration`             | `audioDuration`    | `String?`  | Format: "H:MM:SS" or "MM:SS"      |
| `meta.filesize`              | `meta.filesize`             | `audioFilesize`    | `String?`  | Bytes as string (formatted)        |
| *(scraped/raw)*              | *(raw byte count)*          | `audioFilesizeRaw` | `String?`  | Raw bytes as string                |
| `meta.episode_type`          | `meta.episode_type`         | `episodeType`      | `String?`  | e.g. "full", "trailer", "bonus"    |
| *(scraped from HTML)*        | *(YouTube embed src)*       | `videoUrl`         | `String?`  | YouTube embed URL                  |
| *(scraped from HTML)*        | *(podcast download href)*   | `downloadLink`     | `String?`  | Podcast download URL               |
| *(scraped from HTML)*        | *(podcast player href)*     | `playerLink`       | `String?`  | Podcast player URL                 |
| *(Yoast SEO meta)*          | `og:description`            | `ogDescription`    | `String?`  | Yoast OG description               |
| *(Yoast SEO meta)*          | `og:image`                  | `ogImageUrl`       | `String?`  | Yoast OG image URL                 |
| *(Yoast SEO meta)*          | `link[rel=canonical]`       | `canonicalUrl`     | `String?`  | Yoast canonical URL                |
| `featured_media`             | `featured_media`            | `featuredMediaId`  | `Int?`     | References Media.wpId; 0 = null    |
| `link`                       | `link`                      | `sourceUrl`        | `String`   | Original WordPress permalink       |
| `status`                     | `status`                    | `status`           | `String`   | Default: "publish"                 |
| `tags`                       | `tags`                      | *(via join table)* | `Int[]`    | Array of WP tag IDs                |
| *(taxonomy)*                 | *(series taxonomy term)*    | `seriesId`         | `Int?`     | Resolved during seed               |

### Participant Field Mapping

| WordPress REST API Field     | JSON Path                   | Prisma Field       | Type       | Notes                              |
|------------------------------|-----------------------------|--------------------|------------|------------------------------------|
| `id`                         | `id`                        | `wpId`             | `Int`      | Unique                             |
| `slug`                       | `slug`                      | `slug`             | `String`   | Unique, used for join matching     |
| `title.rendered`             | `title.rendered`            | `name`             | `String`   | Participant display name           |
| *(scraped from HTML)*        | *(title/role text)*         | `professionalTitle`| `String`   | e.g. "Professor, Neuroscience, Icahn School of Medicine"; default `""` |
| `content.rendered`           | `content.rendered`          | `bio`              | `String`   | Full HTML biography; default `""`  |
| *(scraped from HTML)*        | *(papers section exists)*   | `hasPapers`        | `Boolean`  | Has papers/presentations section; default `false` |
| *(scraped from HTML)*        | *(papers section content)*  | `papersText`       | `String`   | Papers/presentations content; default `""` |
| *(Yoast SEO meta)*          | `og:description`            | `ogDescription`    | `String`   | Yoast OG description; default `""` |
| *(Yoast SEO meta)*          | `og:image`                  | `ogImageUrl`       | `String`   | Yoast OG image URL; default `""`   |
| `featured_media`             | `featured_media`            | `featuredMediaId`  | `Int?`     | References Media.wpId; 0 = null    |
| `link`                       | `link`                      | `sourceUrl`        | `String`   | Original WordPress permalink       |

### Tag Field Mapping

| WordPress REST API Field     | JSON Path                   | Prisma Field       | Type       | Notes                              |
|------------------------------|-----------------------------|--------------------|------------|------------------------------------|
| `id`                         | `id`                        | `wpId`             | `Int`      | Unique                             |
| `slug`                       | `slug`                      | `slug`             | `String`   | Unique                             |
| `name`                       | `name`                      | `name`             | `String`   | Tag display name                   |

### Series Field Mapping

| WordPress REST API Field     | JSON Path                   | Prisma Field       | Type       | Notes                              |
|------------------------------|-----------------------------|--------------------|------------|------------------------------------|
| `id`                         | `id`                        | `wpId`             | `Int`      | Unique                             |
| `slug`                       | `slug`                      | `slug`             | `String`   | Unique                             |
| `name`                       | `name`                      | `name`             | `String`   | Series display name                |
| `description`                | `description`               | `description`      | `String`   | Default `""`; may be empty         |

### Page Field Mapping

| WordPress REST API Field     | JSON Path                   | Prisma Field       | Type       | Notes                              |
|------------------------------|-----------------------------|--------------------|------------|------------------------------------|
| `id`                         | `id`                        | `wpId`             | `Int`      | Unique                             |
| `slug`                       | `slug`                      | `slug`             | `String`   | Unique                             |
| `title.rendered`             | `title.rendered`            | `title`            | `String`   | Page title                         |
| `content.rendered`           | `content.rendered`          | `content`          | `String`   | Raw HTML preserved                 |
| `parent`                     | `parent`                    | `parentId`         | `Int?`     | WP parent page ID; 0 = null       |
| `menu_order`                 | `menu_order`                | `menuOrder`        | `Int`      | Default: 0                         |
| `link`                       | `link`                      | `sourceUrl`        | `String`   | Original WordPress permalink       |

### Media Field Mapping

| WordPress REST API Field     | JSON Path                   | Prisma Field       | Type       | Notes                              |
|------------------------------|-----------------------------|--------------------|------------|------------------------------------|
| `id`                         | `id`                        | `wpId`             | `Int`      | Unique                             |
| `source_url`                 | `source_url`                | `sourceUrl`        | `String`   | Full-size image URL                |
| `title.rendered`             | `title.rendered`            | `title`            | `String`   | Media title; default `""`          |
| `alt_text`                   | `alt_text`                  | `altText`          | `String`   | Accessibility text; default `""`   |
| `caption.rendered`           | `caption.rendered`          | `caption`          | `String`   | Media caption HTML; default `""`   |
| `mime_type`                  | `mime_type`                 | `mimeType`         | `String`   | e.g. "image/jpeg"; default `""`    |
| `media_details.width`        | `media_details.width`       | `width`            | `Int?`     | Pixel width                        |
| `media_details.height`       | `media_details.height`      | `height`           | `Int?`     | Pixel height                       |
| `media_details.filesize`     | `media_details.filesize`    | `filesize`         | `Int?`     | Size in bytes                      |
| `media_details.sizes`        | `media_details.sizes`       | `sizes`            | `String`   | JSON string of size variants; default `"{}"`; keys: thumbnail, medium, large, etc. |

### RoundtableParticipant Join Mapping

| Source Field                 | Source File                         | Resolution Strategy                          |
|------------------------------|-------------------------------------|----------------------------------------------|
| `roundtable_slug`            | `roundtable_participants.json`      | Look up `Roundtable` by `slug` to get `id`   |
| `participant_slug`           | `roundtable_participants.json`      | Look up `Participant` by `slug` to get `id`  |

### RoundtableTag Join Mapping

| Source Field                 | Source File                         | Resolution Strategy                          |
|------------------------------|-------------------------------------|----------------------------------------------|
| `roundtable.tags[]`          | `wp_posts.json` (roundtable)       | Each element is a WP tag ID                  |
| *(resolved)*                 | *(in-memory)*                       | Look up `Tag` by `wpId` to get `id`          |
| *(resolved)*                 | *(in-memory)*                       | Look up `Roundtable` by `wpId` to get `id`  |

---

## Seed Strategy

The seed script (`prisma/seed.ts`) populates the database from the crawled JSON files in a specific order to satisfy foreign key constraints.

### Phase 1: Independent Entities (no FK dependencies)

```
1. Read wp_tags.json     → INSERT Tag records
2. Read wp_media.json    → INSERT Media records
3. Read wp_series.json   → INSERT Series records (if available as taxonomy)
4. Read wp_pages.json    → INSERT Page records (parentId set to null initially)
```

### Phase 2: Entities with FK dependencies

```
5. Read wp_participants.json → INSERT Participant records
   - Map featured_media: if value > 0, set featuredMediaId = value; else null

6. Read wp_posts.json (roundtables) → INSERT Roundtable records
   - Map featured_media: if value > 0, set featuredMediaId = value; else null
   - Map series taxonomy term → seriesId (look up Series by wpId)
   - Parse date fields with new Date() for DateTime columns
   - Treat empty string meta values as null
```

### Phase 3: Resolve Page Hierarchy

```
7. For each Page where WP parent > 0:
   - Look up parent Page by wpId
   - UPDATE page SET parentId = parent.id
```

### Phase 4: Join Tables

```
8. Read roundtable_participants.json → INSERT RoundtableParticipant records
   - Each entry contains a roundtable slug and a list of participant slugs
   - For each pair:
     a. Look up Roundtable.id by slug
     b. Look up Participant.id by slug
     c. INSERT into RoundtableParticipant (skip if either lookup fails; log warning)

9. For each Roundtable, iterate its tags[] array → INSERT RoundtableTag records
   - Each element in tags[] is a WP tag ID
   - Look up Tag.id by wpId
   - Look up Roundtable.id (already known from the record)
   - INSERT into RoundtableTag (skip if tag lookup fails; log warning)
```

### Seed Script Pseudocode

```typescript
import { PrismaClient } from "@prisma/client";
import wpPosts from "../data/wp_posts.json";
import wpParticipants from "../data/wp_participants.json";
import wpTags from "../data/wp_tags.json";
import wpPages from "../data/wp_pages.json";
import wpMedia from "../data/wp_media.json";
import wpSeries from "../data/wp_series.json";
import roundtableParticipants from "../data/roundtable_participants.json";

const prisma = new PrismaClient();

async function main() {
  // Phase 1: Independent entities
  for (const tag of wpTags) {
    await prisma.tag.upsert({
      where: { wpId: tag.id },
      update: {},
      create: { wpId: tag.id, slug: tag.slug, name: tag.name },
    });
  }

  for (const media of wpMedia) {
    await prisma.media.upsert({
      where: { wpId: media.id },
      update: {},
      create: {
        wpId: media.id,
        sourceUrl: media.source_url,
        title: media.title?.rendered ?? "",
        altText: media.alt_text || "",
        caption: media.caption?.rendered ?? "",
        mimeType: media.mime_type || "",
        width: media.media_details?.width ?? null,
        height: media.media_details?.height ?? null,
        filesize: media.media_details?.filesize ?? null,
        sizes: JSON.stringify(media.media_details?.sizes ?? {}),
      },
    });
  }

  for (const series of wpSeries) {
    await prisma.series.upsert({
      where: { wpId: series.id },
      update: {},
      create: {
        wpId: series.id,
        slug: series.slug,
        name: series.name,
        description: series.description || "",
      },
    });
  }

  for (const page of wpPages) {
    await prisma.page.upsert({
      where: { wpId: page.id },
      update: {},
      create: {
        wpId: page.id,
        slug: page.slug,
        title: page.title.rendered,
        content: page.content.rendered,
        menuOrder: page.menu_order ?? 0,
        sourceUrl: page.link,
        // parentId resolved in Phase 3
      },
    });
  }

  // Phase 2: FK-dependent entities
  for (const p of wpParticipants) {
    await prisma.participant.upsert({
      where: { wpId: p.id },
      update: {},
      create: {
        wpId: p.id,
        slug: p.slug,
        name: p.title.rendered,
        professionalTitle: p.professionalTitle ?? "",
        bio: p.content.rendered ?? "",
        hasPapers: p.hasPapers ?? false,
        papersText: p.papersText ?? "",
        ogDescription: p.ogDescription ?? "",
        ogImageUrl: p.ogImageUrl ?? "",
        featuredMediaId: p.featured_media > 0 ? p.featured_media : null,
        sourceUrl: p.link,
      },
    });
  }

  for (const r of wpPosts) {
    const seriesTermId = r.series?.[0] ?? null; // first series taxonomy term
    let seriesRecord = null;
    if (seriesTermId) {
      seriesRecord = await prisma.series.findUnique({
        where: { wpId: seriesTermId },
      });
    }

    await prisma.roundtable.upsert({
      where: { wpId: r.id },
      update: {},
      create: {
        wpId: r.id,
        slug: r.slug,
        title: r.title.rendered,
        content: r.content.rendered,
        excerpt: r.excerpt?.rendered ?? "",
        publishedAt: new Date(r.date),
        updatedAt: new Date(r.modified),
        dateRecorded: r.meta?.date_recorded ? new Date(r.meta.date_recorded) : null,
        eventDatetime: r.eventDatetime || null,
        eventStatus: r.eventStatus || null,
        audioFile: r.meta?.audio_file || null,
        audioDuration: r.meta?.duration || null,
        audioFilesize: r.meta?.filesize || null,
        audioFilesizeRaw: r.audioFilesizeRaw || null,
        episodeType: r.meta?.episode_type || null,
        videoUrl: r.videoUrl || null,
        downloadLink: r.downloadLink || null,
        playerLink: r.playerLink || null,
        ogDescription: r.ogDescription || null,
        ogImageUrl: r.ogImageUrl || null,
        canonicalUrl: r.canonicalUrl || null,
        featuredMediaId: r.featured_media > 0 ? r.featured_media : null,
        sourceUrl: r.link,
        status: r.status ?? "publish",
        seriesId: seriesRecord?.id ?? null,
      },
    });
  }

  // Phase 3: Resolve page hierarchy
  for (const page of wpPages) {
    if (page.parent && page.parent > 0) {
      const parentPage = await prisma.page.findUnique({
        where: { wpId: page.parent },
      });
      if (parentPage) {
        await prisma.page.update({
          where: { wpId: page.id },
          data: { parentId: parentPage.id },
        });
      }
    }
  }

  // Phase 4: Join tables
  for (const entry of roundtableParticipants) {
    const roundtable = await prisma.roundtable.findUnique({
      where: { slug: entry.roundtable_slug },
    });
    if (!roundtable) {
      console.warn(`Roundtable not found: ${entry.roundtable_slug}`);
      continue;
    }

    for (const participantSlug of entry.participant_slugs) {
      const participant = await prisma.participant.findUnique({
        where: { slug: participantSlug },
      });
      if (!participant) {
        console.warn(`Participant not found: ${participantSlug}`);
        continue;
      }

      await prisma.roundtableParticipant.upsert({
        where: {
          roundtableId_participantId: {
            roundtableId: roundtable.id,
            participantId: participant.id,
          },
        },
        update: {},
        create: {
          roundtableId: roundtable.id,
          participantId: participant.id,
        },
      });
    }
  }

  // Roundtable → Tag joins
  for (const r of wpPosts) {
    const roundtable = await prisma.roundtable.findUnique({
      where: { wpId: r.id },
    });
    if (!roundtable) continue;

    for (const wpTagId of r.tags ?? []) {
      const tag = await prisma.tag.findUnique({
        where: { wpId: wpTagId },
      });
      if (!tag) {
        console.warn(`Tag not found: wpId=${wpTagId}`);
        continue;
      }

      await prisma.roundtableTag.upsert({
        where: {
          roundtableId_tagId: {
            roundtableId: roundtable.id,
            tagId: tag.id,
          },
        },
        update: {},
        create: {
          roundtableId: roundtable.id,
          tagId: tag.id,
        },
      });
    }
  }

  console.log("Seed complete.");
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
```

---

## Indexes

The following indexes are defined in the schema to optimize common query patterns:

| Model                  | Index Fields                        | Type          | Purpose                                     |
|------------------------|-------------------------------------|---------------|---------------------------------------------|
| Roundtable             | `wpId`                              | Unique        | WordPress ID lookup                         |
| Roundtable             | `slug`                              | Unique + Index| URL routing                                 |
| Roundtable             | `publishedAt`                       | Non-unique    | Chronological listing, date range queries   |
| Roundtable             | `status`                            | Non-unique    | Filter by publish status                    |
| Participant            | `wpId`                              | Unique        | WordPress ID lookup                         |
| Participant            | `slug`                              | Unique + Index| URL routing, join table resolution          |
| Participant            | `name`                              | Non-unique    | Name search and display ordering            |
| RoundtableParticipant  | `(roundtableId, participantId)`     | Unique        | Prevent duplicate join records              |
| RoundtableParticipant  | `roundtableId`                      | Non-unique    | "Participants for roundtable X"             |
| RoundtableParticipant  | `participantId`                     | Non-unique    | "Roundtables for participant Y"             |
| Tag                    | `wpId`                              | Unique        | WordPress ID lookup                         |
| Tag                    | `slug`                              | Unique + Index| URL routing                                 |
| RoundtableTag          | `(roundtableId, tagId)`             | Unique        | Prevent duplicate join records              |
| RoundtableTag          | `roundtableId`                      | Non-unique    | "Tags for roundtable X"                     |
| RoundtableTag          | `tagId`                             | Non-unique    | "Roundtables with tag Y"                    |
| Series                 | `wpId`                              | Unique        | WordPress ID lookup                         |
| Series                 | `slug`                              | Unique + Index| URL routing                                 |
| Page                   | `wpId`                              | Unique        | WordPress ID lookup                         |
| Page                   | `slug`                              | Unique + Index| URL routing                                 |
| Page                   | `parentId`                          | Non-unique    | Child page queries                          |
| Media                  | `wpId`                              | Unique + Index| WordPress ID lookup, FK target              |
| SiteConfig             | `key`                               | Unique        | Config lookup by key                        |

---

## Migration Notes

### Initial Migration

```bash
# Generate the initial migration from the Prisma schema
npx prisma migrate dev --name init

# Seed the database
npx prisma db seed
```

### Data Transformation Rules

1. **WordPress ID 0 means null** -- When `featured_media` or `parent` is `0` in the WordPress API response, store it as `null` in the database. WordPress uses 0 to indicate "no value" for these fields.

2. **Empty string meta means null** -- Meta fields like `date_recorded`, `audio_file`, `duration` may be empty strings `""` in the API response. Treat these as `null`.

3. **HTML entity decoding** -- `title.rendered` values may contain HTML entities (e.g., `&#8217;` for right single quote, `&amp;` for ampersand). Decode these before storing, or store as-is and decode at render time. The schema stores them as-is for fidelity.

4. **Date parsing** -- WordPress dates are in ISO 8601 format (e.g., `2024-03-15T14:30:00`). These are in the site's local timezone (typically America/New_York for Helix Center). Consider normalizing to UTC.

5. **Slug uniqueness** -- Slugs are guaranteed unique within each WordPress post type, so they are safe to use as unique constraints in the corresponding Prisma models.

6. **Page hierarchy resolution** -- Pages must be inserted in two passes: first without `parentId`, then update with resolved parent references. This avoids FK constraint violations from insertion order.

7. **Join table population from scraped data** -- The `roundtable_participants.json` file is produced by scraping roundtable detail pages (not from the REST API), so its data format differs from API responses. Each entry maps a roundtable slug to an array of participant slugs extracted from HTML links.

8. **Idempotent seeding** -- The seed script uses `upsert` operations throughout so it can be safely re-run without creating duplicates. This supports incremental data updates.

9. **HTML-scraped fields** -- Several fields are populated by scraping the rendered HTML page rather than from the REST API. For roundtables: `eventDatetime`, `eventStatus`, `videoUrl`, `downloadLink`, and `playerLink` are extracted from specific DOM elements. For participants: `professionalTitle`, `hasPapers`, and `papersText` are scraped from the participant detail page.

10. **Yoast SEO metadata** -- The `ogDescription`, `ogImageUrl`, and `canonicalUrl` fields are extracted from Yoast SEO `<meta>` and `<link>` tags in the page `<head>`. These are available on both roundtable and participant pages.

11. **Media size variants as JSON** -- The `sizes` field on Media stores WordPress responsive image size data as a JSON string. The object keys are size names (e.g. `thumbnail`, `medium`, `medium_large`, `large`, `full`) and values contain `url`, `width`, and `height`. Parse with `JSON.parse()` at query time.

### Future Considerations

- **PostgreSQL migration** -- To move to PostgreSQL, change the `provider` in `datasource db` and update the `DATABASE_URL`. The schema is compatible with both providers. SQLite-specific limitations (no native enum types, limited concurrent writes) would be resolved.
- **Full-text search** -- SQLite FTS5 can be added via a raw SQL migration for searching roundtable content and participant bios. PostgreSQL offers `tsvector`/`tsquery` natively.
- **Image optimization** -- The `Media` model stores original source URLs. A build step should download, optimize (WebP/AVIF), and generate responsive sizes. Add `localPath` and `optimizedUrl` fields when this pipeline is implemented.
- **Content transformation** -- A future migration could add a `contentMdx` field alongside the raw HTML `content` field, storing pre-processed MDX for faster rendering.
