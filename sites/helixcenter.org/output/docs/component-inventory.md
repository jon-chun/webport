# Component Inventory

Next.js 14 App Router + Tailwind CSS rebuild of helixcenter.org.

This document catalogs every React component required for the Helix Center site rebuild, organized by functional area. Each entry includes the file path, props interface, behavior description, and responsive design notes.

---

## Layout Components

### RootLayout

| | |
|---|---|
| **File** | `src/app/layout.tsx` |
| **Type** | Server Component |

**Props Interface**

```tsx
interface RootLayoutProps {
  children: React.ReactNode;
}
```

**Behavior**

- Wraps the entire application with the `<html>` and `<body>` tags.
- Loads the site-wide font stack via `next/font/google` (the Helix Center uses a serif body font and sans-serif headings).
- Imports `globals.css` for Tailwind base/components/utilities and any CSS custom properties.
- Sets default `<head>` metadata via the Next.js `metadata` export: site title template (`"%s | The Helix Center"`), description, Open Graph defaults, and favicon.
- Renders `<Header />` above `{children}` and `<Footer />` below.

**Responsive Notes**

- No responsive-specific behavior; layout delegates responsiveness to child components.

---

### Header

| | |
|---|---|
| **File** | `src/components/layout/Header.tsx` |
| **Type** | Client Component (`"use client"`) |

**Props Interface**

```tsx
// No props - reads navigation data from a shared constant or server action.
```

**Behavior**

- Renders a fixed/sticky top bar with the Helix Center logo (linked to `/`) on the left.
- Desktop: displays `<Navigation />` inline to the right of the logo.
- Mobile (below `lg` breakpoint): hides `<Navigation />` and shows a hamburger icon button that toggles `<MobileMenu />`.
- Nav links: **About** (dropdown), **Roundtables** (`/roundtables`), **Participants** (`/participants`), **Contact** (`/contact`), **Donate** (`/donate`).
- The **About** dropdown contains sub-links: About (`/about`), Board of Directors (`/about/board-of-directors`), Executive Committee (`/about/executive-committee`).
- Active link is highlighted based on the current pathname via `usePathname()`.

**Responsive Notes**

- `hidden lg:flex` for desktop nav; `lg:hidden` for hamburger button.
- Header height: `h-16` on mobile, `h-20` on desktop. Page content has corresponding top padding.

---

### Footer

| | |
|---|---|
| **File** | `src/components/layout/Footer.tsx` |
| **Type** | Server Component |

**Props Interface**

```tsx
// No props.
```

**Behavior**

- Renders a dark-background footer with three sections:
  1. **Social icons**: `<SocialLinks />` component rendering Facebook, Twitter/X, YouTube, Instagram, and Apple Podcasts icons.
  2. **Utility links**: `<RSSLink />` for the RSS feed and a "View Map" link pointing to a Google Maps embed or external link for the Helix Center address.
  3. **Copyright**: `"Copyright (c) {currentYear} The Helix Center. All rights reserved."`

**Responsive Notes**

- Single-column stacked layout on mobile; horizontal row on `md` and above.
- Social icons are centered on mobile, left-aligned on desktop.

---

### Navigation

| | |
|---|---|
| **File** | `src/components/layout/Navigation.tsx` |
| **Type** | Client Component (`"use client"`) |

**Props Interface**

```tsx
// No props.
```

**Behavior**

- Renders the desktop horizontal nav bar.
- Each top-level link is a `<Link>` from `next/link`.
- The "About" item renders a dropdown on hover/focus using a `<div>` with `group` and `group-hover:block` Tailwind classes (or a controlled state for accessibility).
- Dropdown items: About, Board of Directors, Executive Committee.
- Keyboard accessible: dropdown opens on Enter/Space, closes on Escape, arrow keys navigate items.

**Responsive Notes**

- Only visible at `lg` breakpoint and above (`hidden lg:flex`).

---

### MobileMenu

| | |
|---|---|
| **File** | `src/components/layout/MobileMenu.tsx` |
| **Type** | Client Component (`"use client"`) |

**Props Interface**

```tsx
interface MobileMenuProps {
  isOpen: boolean;
  onClose: () => void;
}
```

**Behavior**

- Slide-out drawer from the right side of the screen.
- Renders all nav links vertically with larger touch targets (`py-3` minimum).
- "About" section is an expandable accordion (tap to toggle sub-links).
- Overlay backdrop (`bg-black/50`) behind the menu; clicking it calls `onClose`.
- Traps focus within the menu when open.
- Closes on Escape key.
- Applies `overflow-hidden` to `<body>` when open to prevent background scroll.

**Responsive Notes**

- Only rendered below `lg` breakpoint. At `lg` and above, `<Navigation />` takes over.

---

## Roundtable Components

### RoundtableCard

| | |
|---|---|
| **File** | `src/components/roundtables/RoundtableCard.tsx` |
| **Type** | Server Component |

**Props Interface**

```tsx
interface RoundtableCardProps {
  roundtable: {
    id: number;
    slug: string;
    title: string;
    excerpt: string;              // HTML string
    publishedAt: Date;
    eventDatetime: string | null; // Pre-formatted date/time string
    eventStatus: string | null;   // "Future Event" | "Past Event"
    audioFile: string | null;
    featuredImage: { sourceUrl: string; altText: string } | null;
    participants: {
      participant: { slug: string; name: string };
    }[];
  };
}
```

**Behavior**

- Renders a card linking to `/roundtables/{slug}`.
- Displays the featured image at the top (with `next/image`, `h-48`, `object-cover`). No image section is rendered when `featuredImage` is null.
- Below the image, a metadata row displays:
  - **Date**: shows `eventDatetime` if available, otherwise falls back to `publishedAt` formatted as a short date (e.g., "Oct 4, 2025").
  - **Event status badge**: when `eventStatus` is present, renders a colored inline badge -- green (`bg-green-100 text-green-800`) for "Future Event", gray (`bg-gray-100 text-gray-600`) for "Past Event".
  - **Audio badge**: when `audioFile` is present, renders a small "Audio" badge in `bg-helix-blue/10 text-helix-blue`.
- Title rendered as `<h3>` with `font-serif font-semibold`.
- Below the title: participant names listed as a comma-separated string (single line, `line-clamp-1`).

**Responsive Notes**

- Card width is controlled by the parent grid. Internal padding: `p-4`.
- Image height: `h-48`.

---

### RoundtableList

| | |
|---|---|
| **File** | `src/components/roundtables/RoundtableList.tsx` |
| **Type** | Server Component |

**Props Interface**

```tsx
interface RoundtableListProps {
  roundtables: RoundtableCardProps["roundtable"][];
  currentPage: number;
  totalPages: number;
}
```

**Behavior**

- Renders a grid of `<RoundtableCard />` components.
- Grid layout: 1 column on mobile, 2 on `md`, 3 on `lg`.
- Below the grid, renders `<Pagination />` for navigating between pages.
- When the list is empty, shows a "No roundtables found" message.

**Responsive Notes**

- Grid gap: `gap-4` on mobile, `gap-6` on `md`, `gap-8` on `lg`.

---

### Roundtable Detail Page

| | |
|---|---|
| **File** | `src/app/roundtables/[slug]/page.tsx` |
| **Type** | Server Component (with Client Component islands) |

**Data Fetching**

- Uses `getRoundtableBySlug(params.slug)` to fetch data; returns `notFound()` if no roundtable exists.
- `generateStaticParams()` pre-renders all slugs via `getAllRoundtableSlugs()`.
- `generateMetadata()` produces Open Graph metadata using `ogDescription` (with fallback to stripped excerpt) and `ogImageUrl` when available.

**Behavior**

- Renders the full roundtable detail page inside a `max-w-4xl mx-auto` container.
- **Breadcrumbs**: inline nav linking back to `/roundtables` with the current title as plain text.
- **Featured image**: full-width, height-constrained (`h-64 md:h-96`), rounded, using `next/image` with `priority` loading. Only rendered when `featuredImage` is present.
- **Title**: `<h1>` with `text-4xl font-serif`.
- **Event date/time and status**: a flex row below the title displaying:
  - `eventDatetime` as a formatted date string (or `dateRecorded` formatted as a long date if `eventDatetime` is absent).
  - `eventStatus` as a colored pill badge (`rounded-full`): green (`bg-green-100 text-green-800`) for "Future Event", gray (`bg-gray-100 text-gray-700`) for "Past Event".
- **Audio player**: `<AudioPlayer />` rendered when `audioFile` is present, receiving `src`, `duration`, and `title` props.
- **YouTube video embed**: when `videoUrl` is present, renders a responsive 16:9 iframe (`aspect-video`) inside a rounded container. The iframe supports accelerometer, autoplay, clipboard-write, encrypted-media, gyroscope, and picture-in-picture via the `allow` attribute, and has `allowFullScreen` enabled.
- **Participants section**: heading "Participants" followed by `<ParticipantChips />` linking to each participant's detail page.
- **Content**: full WordPress HTML rendered via `dangerouslySetInnerHTML` with `wp-content` class.
- **Tags/Topics**: when tags exist, renders a "Topics" section below a border separator with pill-shaped tag badges.
- **SEO**: `<SEOJsonLd />` with `Event` schema including `name`, `description`, `startDate`, `location` (The Helix Center address), and `performer` (participant list).

**Responsive Notes**

- Featured image: `h-64` on mobile, `h-96` on `md` and above.
- Content area: `max-w-4xl mx-auto` for comfortable reading width.
- Event info row uses `flex-wrap` to stack gracefully on narrow screens.

---

### AudioPlayer

| | |
|---|---|
| **File** | `src/components/roundtables/AudioPlayer.tsx` |
| **Type** | Client Component (`"use client"`) |

**Props Interface**

```tsx
interface AudioPlayerProps {
  src: string;                    // MP3 URL from media.helixcenter.org
  duration?: string;              // Pre-formatted duration, e.g., "1:08:20"
}
```

**Behavior**

- Custom HTML5 audio player (does not use native `<audio controls>`).
- Play/pause toggle button with icon swap.
- Progress bar: clickable/draggable `<input type="range">` or custom div showing playback position.
- Time display: current time / total duration (e.g., "12:34 / 1:08:20").
- Uses `useRef` for the `<audio>` element and `useState` for playback state.
- Handles `onTimeUpdate`, `onLoadedMetadata`, `onEnded` events.
- Preload set to `"metadata"` to avoid downloading the full file until play is pressed.
- Error state: shows "Audio unavailable" message if the MP3 fails to load.

**Responsive Notes**

- Full width of its container.
- On mobile, play button and time stack vertically if needed; on `md` and above, all controls are in a single horizontal row.

---

### ParticipantChips

| | |
|---|---|
| **File** | `src/components/roundtables/ParticipantChips.tsx` |
| **Type** | Server Component |

**Props Interface**

```tsx
interface ParticipantChipsProps {
  participants: {
    slug: string;
    name: string;
  }[];
  maxVisible?: number;            // Default: undefined (show all)
}
```

**Behavior**

- Renders an inline `flex flex-wrap` list of participant names as small pill-shaped badges.
- Each chip is a `<Link>` to `/participants/{slug}`.
- Chips styled with a subtle background (`bg-stone-100`), rounded corners, and hover state.
- If `maxVisible` is set and participants exceed that count, shows "+N more" as the last chip.

**Responsive Notes**

- Chips wrap naturally. Font size: `text-xs` on mobile, `text-sm` on `md`.

---

## Participant Components

### ParticipantCard

| | |
|---|---|
| **File** | `src/components/participants/ParticipantCard.tsx` |
| **Type** | Server Component |

**Props Interface**

```tsx
interface ParticipantCardProps {
  participant: {
    slug: string;
    name: string;
    professionalTitle: string;
    bio: string;                  // HTML, will be truncated
    featuredImage: { sourceUrl: string; altText: string } | null;
    roundtables: { roundtable: { id: number } }[];
  };
}
```

**Behavior**

- Card linking to `/participants/{slug}`.
- Headshot image at the top (`h-48`, `object-cover object-top`) via `next/image`. No image section is rendered when `featuredImage` is null.
- Name as `<h3>` with `font-serif font-semibold`.
- **Professional title** displayed directly under the name (`text-sm text-gray-500 mt-0.5 line-clamp-1`) when present.
- Bio stripped of HTML tags and truncated to 120 characters, rendered as a single `line-clamp-2` paragraph.
- Roundtable count shown at the bottom (e.g., "3 roundtables") in `text-xs text-gray-400`.

**Responsive Notes**

- Card width determined by parent grid.
- Image height: `h-48`.

---

### ParticipantGrid

| | |
|---|---|
| **File** | `src/components/participants/ParticipantGrid.tsx` |
| **Type** | Client Component (`"use client"`) |

**Props Interface**

```tsx
interface ParticipantGridProps {
  participants: ParticipantCardProps["participant"][];
}
```

**Behavior**

- Renders `<AlphabetFilter />` above the grid.
- Filters participants client-side based on the selected letter (matched against the first character of the last name, which is derived by splitting on the last space in the name).
- Grid layout: 2 columns on mobile, 3 on `md`, 4 on `lg`.
- Shows "No participants found for [letter]" when the filtered list is empty.

**Responsive Notes**

- Grid gap: `gap-4` on mobile, `gap-6` on `lg`.

---

### Participant Detail Page

| | |
|---|---|
| **File** | `src/app/participants/[slug]/page.tsx` |
| **Type** | Server Component |

**Data Fetching**

- Uses `getParticipantBySlug(params.slug)` to fetch data; returns `notFound()` if no participant exists.
- `generateStaticParams()` pre-renders all slugs via `getAllParticipantSlugs()`.
- `generateMetadata()` produces Open Graph metadata using `ogDescription` (with fallback to stripped bio, first 160 characters) and `ogImageUrl` when available.

**Behavior**

- Renders the full participant detail page inside a `max-w-4xl mx-auto` container.
- **Breadcrumbs**: inline nav linking back to `/participants` with the current participant name as plain text.
- **Headshot and bio layout**: uses `md:flex gap-8` to place the headshot beside the name/bio on desktop, stacked on mobile.
  - Headshot: `w-48 h-48 rounded-lg` using `next/image` with `priority` loading. Only rendered when `featuredImage` is present.
  - Name: `<h1>` with `text-4xl font-serif`.
  - **Professional title**: displayed directly under the `<h1>` name as `text-lg text-gray-600 mb-6` when present. When absent, a spacer div provides consistent vertical rhythm.
  - Bio: full WordPress HTML rendered via `dangerouslySetInnerHTML` with `wp-content` class.
- **Papers & Presentations section**: rendered when `hasPapers` is truthy and `papersText` is present. Displays a "Papers & Presentations" heading (`text-2xl font-serif`) followed by the papers HTML rendered via `dangerouslySetInnerHTML` with `wp-content prose` classes.
- **Roundtable Discussions section**: when the participant has associated roundtables, renders a "Roundtable Discussions" heading followed by a vertical list of linked roundtable cards. Each card shows a thumbnail image (when available), the roundtable title, and a formatted date. Cards have hover states (`hover:border-helix-blue hover:bg-gray-50`).
- **SEO**: `<SEOJsonLd />` with `Person` schema including `name`, `url`, `image`, and `description`.

**Responsive Notes**

- On mobile: headshot and bio stack vertically.
- On `md` and above: headshot and bio sit side-by-side via `md:flex`.
- Roundtable card thumbnails are `w-16 h-16` with `flex-shrink-0` to maintain size at all breakpoints.

---

### AlphabetFilter

| | |
|---|---|
| **File** | `src/components/participants/AlphabetFilter.tsx` |
| **Type** | Client Component (`"use client"`) |

**Props Interface**

```tsx
interface AlphabetFilterProps {
  activeLetter: string | null;    // null = "All"
  availableLetters: string[];     // Letters that have participants
  onSelect: (letter: string | null) => void;
}
```

**Behavior**

- Renders a horizontal row of buttons for each letter A through Z, plus an "All" button.
- The active letter button is visually highlighted (`bg-primary text-white` or similar).
- Letters not present in `availableLetters` are rendered as disabled/dimmed (`opacity-50 cursor-not-allowed`).
- Clicking a letter calls `onSelect` with the letter; clicking "All" calls `onSelect(null)`.

**Responsive Notes**

- On mobile, the letter row wraps or scrolls horizontally (`overflow-x-auto`).
- Button sizes: `w-8 h-8 text-sm` on mobile, `w-10 h-10 text-base` on `md`.

---

## Page Components

### PageContent

| | |
|---|---|
| **File** | `src/components/pages/PageContent.tsx` |
| **Type** | Server Component |

**Props Interface**

```tsx
interface PageContentProps {
  html: string;                   // Raw WordPress HTML content
  className?: string;
}
```

**Behavior**

- Renders WordPress HTML content using `dangerouslySetInnerHTML`.
- Wraps the output in a `<div>` with Tailwind Typography plugin classes: `prose prose-stone lg:prose-lg max-w-none`.
- The prose styles handle headings, paragraphs, lists, blockquotes, images, links, and tables from the WordPress content.
- Images within the HTML are displayed as-is (they reference `media.helixcenter.org` URLs and do not need processing).

**Responsive Notes**

- The `prose` class handles responsive typography automatically.
- `lg:prose-lg` increases base font size on large screens.

---

### ContactForm

| | |
|---|---|
| **File** | `src/components/pages/ContactForm.tsx` |
| **Type** | Client Component (`"use client"`) |

**Props Interface**

```tsx
// No props.
```

**Behavior**

- Renders a form with three fields:
  - **Name** (`<input type="text">`, required)
  - **Email** (`<input type="email">`, required)
  - **Message** (`<textarea>`, required)
- Submit button posts to a server action or API route (`/api/contact`).
- Client-side validation via HTML5 `required` and `type="email"`.
- Shows loading state on the submit button during submission.
- On success: displays a "Thank you" confirmation message and resets the form.
- On error: displays an error message above the form.
- Uses `useFormStatus` or `useTransition` for pending state.

**Responsive Notes**

- Form fields are full width. Max container width: `max-w-lg mx-auto`.

---

### DonateButton

| | |
|---|---|
| **File** | `src/components/pages/DonateButton.tsx` |
| **Type** | Server Component |

**Props Interface**

```tsx
interface DonateButtonProps {
  className?: string;
}
```

**Behavior**

- Renders a prominent call-to-action button/link for donations.
- Links to the donate page or external donation URL.
- Styled as a large, visually distinct button (`bg-primary text-white px-8 py-4 text-lg font-semibold rounded-lg`).
- Hover/focus states with color shift and subtle shadow.

**Responsive Notes**

- Full width on mobile (`w-full`), auto width on `md` and above (`md:w-auto`).

---

## Shared Components

### SearchBar

| | |
|---|---|
| **File** | `src/components/shared/SearchBar.tsx` |
| **Type** | Client Component (`"use client"`) |

**Props Interface**

```tsx
interface SearchBarProps {
  placeholder?: string;           // Default: "Search roundtables..."
}
```

**Behavior**

- Text input with a search icon.
- Debounces input (300ms) before firing a query.
- Fetches results from `/api/search?q={query}` and displays them in a dropdown below the input.
- Results show roundtable titles and participant names, each linking to their detail page.
- Dropdown closes on outside click or Escape key.
- Shows "No results found" for empty result sets.
- Shows a loading spinner while the fetch is in-flight.

**Responsive Notes**

- On mobile in the header, expands to full width when focused.
- Dropdown results: full width of the search bar, max-height with scroll.

---

### Pagination

| | |
|---|---|
| **File** | `src/components/shared/Pagination.tsx` |
| **Type** | Server Component |

**Props Interface**

```tsx
interface PaginationProps {
  currentPage: number;
  totalPages: number;
  basePath: string;               // e.g., "/roundtables"
}
```

**Behavior**

- Renders page navigation: Previous arrow, page number buttons, Next arrow.
- Uses `<Link>` components pointing to `{basePath}?page={n}`.
- Current page is visually highlighted and not clickable.
- Previous is disabled/hidden on page 1; Next is disabled/hidden on the last page.
- For large page counts (10+), uses ellipsis: `1 2 ... 5 6 7 ... 12 13`.

**Responsive Notes**

- On mobile, shows only Previous/Next arrows and the current page indicator.
- On `md` and above, shows the full page number list.

---

### Breadcrumbs

| | |
|---|---|
| **File** | `src/components/shared/Breadcrumbs.tsx` |
| **Type** | Server Component |

**Props Interface**

```tsx
interface BreadcrumbItem {
  label: string;
  href?: string;                  // Omitted for the current/last item
}

interface BreadcrumbsProps {
  items: BreadcrumbItem[];
}
```

**Behavior**

- Renders a horizontal breadcrumb trail separated by `>` or `/` chevrons.
- All items except the last are rendered as `<Link>` elements.
- The last item is rendered as plain text (current page).
- Wrapped in a `<nav aria-label="Breadcrumb">` with an `<ol>` for semantic markup.
- Example: `Home > About > Board of Directors`

**Responsive Notes**

- On mobile, long breadcrumb trails truncate middle items with an ellipsis.
- Text size: `text-sm` across all breakpoints.

---

### SEOJsonLd

| | |
|---|---|
| **File** | `src/components/shared/SEOJsonLd.tsx` |
| **Type** | Server Component |

**Props Interface**

```tsx
interface SEOJsonLdProps {
  type: "Event" | "Person";
  data: Record<string, unknown>;
}
```

**Behavior**

- Renders a `<script type="application/ld+json">` tag in the page head area.
- For `Event` type (roundtables): includes `name`, `startDate`, `description`, `performer` (participants), `location` (The Helix Center), `url`, and `recordedIn` (audio URL if available).
- For `Person` type (participants): includes `name`, `description` (bio excerpt), `image` (headshot URL), `url`.
- Data is serialized with `JSON.stringify`.

**Responsive Notes**

- Not a visual component; no responsive considerations.

---

### SocialLinks

| | |
|---|---|
| **File** | `src/components/shared/SocialLinks.tsx` |
| **Type** | Server Component |

**Props Interface**

```tsx
interface SocialLinksProps {
  className?: string;
  iconSize?: number;              // Default: 24
}
```

**Behavior**

- Renders a row of social media icon links:
  - Facebook: `https://www.facebook.com/helixcenter`
  - Twitter/X: `https://twitter.com/TheHelixCenter`
  - YouTube: Helix Center YouTube channel
  - Instagram: Helix Center Instagram
  - Apple Podcasts: Helix Center podcast listing
- Each link opens in a new tab (`target="_blank" rel="noopener noreferrer"`).
- Icons sourced from `lucide-react` or a similar icon library.
- Each link has an `aria-label` for accessibility (e.g., `aria-label="Facebook"`).

**Responsive Notes**

- Icons are spaced with `gap-4`. Size scales with `iconSize` prop.

---

### RSSLink

| | |
|---|---|
| **File** | `src/components/shared/RSSLink.tsx` |
| **Type** | Server Component |

**Props Interface**

```tsx
interface RSSLinkProps {
  className?: string;
}
```

**Behavior**

- Renders an RSS icon with a link to the site's RSS feed (`/feed.xml` or `/rss`).
- Opens in a new tab.
- Includes `aria-label="RSS Feed"`.

**Responsive Notes**

- Inline icon, no special responsive behavior.

---

## Component Dependency Tree

```
RootLayout
├── Header
│   ├── Navigation (desktop)
│   │   └── About Dropdown
│   └── MobileMenu (mobile)
├── {children} ← page content
│   ├── /roundtables
│   │   └── RoundtableList
│   │       ├── RoundtableCard[]
│   │       │   └── ParticipantChips
│   │       └── Pagination
│   ├── /roundtables/[slug]
│   │   └── RoundtableDetailPage
│   │       ├── AudioPlayer
│   │       ├── YouTube Video Embed (iframe)
│   │       ├── ParticipantChips
│   │       ├── Content (dangerouslySetInnerHTML)
│   │       └── SEOJsonLd (Event)
│   ├── /participants
│   │   └── ParticipantGrid
│   │       ├── AlphabetFilter
│   │       └── ParticipantCard[]
│   ├── /participants/[slug]
│   │   └── ParticipantDetailPage
│   │       ├── Content (dangerouslySetInnerHTML)
│   │       ├── Papers & Presentations (conditional)
│   │       ├── Roundtable Discussions list
│   │       └── SEOJsonLd (Person)
│   ├── /about/* (static pages)
│   │   ├── Breadcrumbs
│   │   └── PageContent
│   ├── /contact
│   │   └── ContactForm
│   └── /donate
│       └── DonateButton
└── Footer
    ├── SocialLinks
    └── RSSLink
```
