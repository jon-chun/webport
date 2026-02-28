import { PrismaClient } from "@prisma/client";
import * as fs from "fs";
import * as path from "path";

const prisma = new PrismaClient();

const INPUT_DIR = path.resolve(__dirname, "../../../input");

function readJson(filename: string): any {
  const filepath = path.join(INPUT_DIR, filename);
  if (!fs.existsSync(filepath)) {
    console.warn(`  Warning: ${filename} not found, skipping`);
    return null;
  }
  return JSON.parse(fs.readFileSync(filepath, "utf-8"));
}

function parseDate(value: string): Date | null {
  if (!value) return null;
  // Handle DD-MM-YYYY format
  const ddmmyyyy = value.match(/^(\d{2})-(\d{2})-(\d{4})$/);
  if (ddmmyyyy) {
    const [, dd, mm, yyyy] = ddmmyyyy;
    const d = new Date(`${yyyy}-${mm}-${dd}`);
    return isNaN(d.getTime()) ? null : d;
  }
  const d = new Date(value);
  return isNaN(d.getTime()) ? null : d;
}

function decodeHtmlEntities(text: string): string {
  return text
    .replace(/&#8217;/g, "\u2019")
    .replace(/&#8216;/g, "\u2018")
    .replace(/&#8220;/g, "\u201C")
    .replace(/&#8221;/g, "\u201D")
    .replace(/&#8211;/g, "\u2013")
    .replace(/&#8212;/g, "\u2014")
    .replace(/&#038;/g, "&")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'");
}

async function main() {
  console.log("=== Seeding Helix Center Database ===");
  console.log(`Input directory: ${INPUT_DIR}`);

  // ── Media ───────────────────────────────────────────────
  console.log("\nSeeding media...");
  const mediaData = readJson("wp_media.json");
  if (mediaData) {
    let count = 0;
    for (const item of mediaData) {
      const md = item.media_details || {};

      // Build sizes JSON from media_details.sizes
      const sizesMap: Record<string, { url: string; w: number; h: number }> =
        {};
      if (md.sizes) {
        for (const [key, val] of Object.entries(md.sizes) as [string, any][]) {
          sizesMap[key] = {
            url: val.source_url || "",
            w: val.width || 0,
            h: val.height || 0,
          };
        }
      }

      await prisma.media.upsert({
        where: { wpId: item.id },
        update: {},
        create: {
          wpId: item.id,
          sourceUrl: item.source_url || "",
          title: decodeHtmlEntities(item.title?.rendered || ""),
          altText: item.alt_text || "",
          caption: item.caption?.rendered || "",
          mimeType: item.mime_type || "",
          width: md.width || null,
          height: md.height || null,
          filesize: md.filesize || null,
          sizes: JSON.stringify(sizesMap),
        },
      });
      count++;
    }
    console.log(`  Created ${count} media records`);
  }

  // ── Tags ────────────────────────────────────────────────
  console.log("\nSeeding tags...");
  const tagsData = readJson("wp_tags.json");
  if (tagsData) {
    let count = 0;
    for (const tag of tagsData) {
      await prisma.tag.upsert({
        where: { wpId: tag.id },
        update: {},
        create: {
          wpId: tag.id,
          slug: tag.slug,
          name: decodeHtmlEntities(tag.name),
        },
      });
      count++;
    }
    console.log(`  Created ${count} tag records`);
  }

  // ── Series ─────────────────────────────────────────────
  console.log("\nSeeding series...");
  const postsData = readJson("wp_posts.json");
  const seriesData = readJson("wp_series.json");
  if (seriesData) {
    for (const series of seriesData) {
      await prisma.series.upsert({
        where: { wpId: series.id },
        update: {},
        create: {
          wpId: series.id,
          slug: series.slug,
          name: decodeHtmlEntities(series.name),
          description: series.description || "",
        },
      });
    }
    console.log(`  Created ${seriesData.length} series records`);
  } else {
    // Fallback: extract series from embedded term data in posts
    const seriesSet = new Map<
      number,
      { id: number; slug: string; name: string }
    >();
    if (postsData) {
      for (const post of postsData) {
        const embedded = post._embedded;
        if (embedded?.["wp:term"]) {
          for (const termGroup of embedded["wp:term"]) {
            if (Array.isArray(termGroup)) {
              for (const term of termGroup) {
                if (term.taxonomy === "series" && !seriesSet.has(term.id)) {
                  seriesSet.set(term.id, {
                    id: term.id,
                    slug: term.slug,
                    name: decodeHtmlEntities(term.name),
                  });
                }
              }
            }
          }
        }
      }
    }
    for (const series of seriesSet.values()) {
      await prisma.series.upsert({
        where: { wpId: series.id },
        update: {},
        create: {
          wpId: series.id,
          slug: series.slug,
          name: series.name,
        },
      });
    }
    console.log(`  Created ${seriesSet.size} series records (from embedded data)`);
  }

  // ── Pages ───────────────────────────────────────────────
  console.log("\nSeeding pages...");
  const pagesData = readJson("wp_pages.json");
  if (pagesData) {
    // First pass: create all pages without parent references
    for (const page of pagesData) {
      await prisma.page.upsert({
        where: { wpId: page.id },
        update: {},
        create: {
          wpId: page.id,
          slug: page.slug,
          title: decodeHtmlEntities(page.title?.rendered || ""),
          content: page.content?.rendered || "",
          menuOrder: page.menu_order || 0,
          sourceUrl: page.link || "",
        },
      });
    }
    // Second pass: set parent references
    for (const page of pagesData) {
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
    console.log(`  Created ${pagesData.length} page records`);
  }

  // ── Participants ────────────────────────────────────────
  console.log("\nSeeding participants...");
  const participantsData = readJson("wp_participants.json");
  const participantTitles = readJson("participant_titles.json") || {};
  if (participantsData) {
    let count = 0;
    for (const p of participantsData) {
      const featuredMediaId = p.featured_media || null;
      let mediaExists = false;
      if (featuredMediaId) {
        const media = await prisma.media.findUnique({
          where: { wpId: featuredMediaId },
        });
        mediaExists = !!media;
      }

      // Merge scraped title data
      const titleData = participantTitles[p.slug] || {};
      const yoast = p.yoast_head_json || {};

      await prisma.participant.upsert({
        where: { wpId: p.id },
        update: {},
        create: {
          wpId: p.id,
          slug: p.slug,
          name: decodeHtmlEntities(p.title?.rendered || ""),
          professionalTitle: titleData.professional_title || "",
          bio: p.content?.rendered || "",
          hasPapers: titleData.has_papers || false,
          papersText: titleData.papers_text || "",
          ogDescription: yoast.og_description || "",
          ogImageUrl: yoast.og_image?.[0]?.url || "",
          sourceUrl: p.link || "",
          featuredMediaId: mediaExists ? featuredMediaId : null,
        },
      });
      count++;
    }
    console.log(`  Created ${count} participant records`);
  }

  // ── Roundtables ─────────────────────────────────────────
  console.log("\nSeeding roundtables...");
  const roundtableDetails = readJson("roundtable_details.json") || {};
  if (postsData) {
    let count = 0;
    for (const post of postsData) {
      const meta = post.meta || {};
      const yoast = post.yoast_head_json || {};
      const details = roundtableDetails[post.slug] || {};
      const featuredMediaId = post.featured_media || null;

      let mediaExists = false;
      if (featuredMediaId) {
        const media = await prisma.media.findUnique({
          where: { wpId: featuredMediaId },
        });
        mediaExists = !!media;
      }

      // Find series ID
      let seriesWpId: number | null = null;
      if (post.series && post.series.length > 0) {
        seriesWpId = post.series[0];
      }
      let seriesExists = false;
      if (seriesWpId) {
        const s = await prisma.series.findUnique({ where: { wpId: seriesWpId } });
        seriesExists = !!s;
      }

      await prisma.roundtable.upsert({
        where: { wpId: post.id },
        update: {},
        create: {
          wpId: post.id,
          slug: post.slug,
          title: decodeHtmlEntities(post.title?.rendered || ""),
          content: post.content?.rendered || "",
          excerpt: post.excerpt?.rendered || "",
          publishedAt: new Date(post.date),
          updatedAt: new Date(post.modified),
          dateRecorded: meta.date_recorded
            ? parseDate(meta.date_recorded)
            : null,
          eventDatetime: details.event_datetime || null,
          eventStatus: details.event_status || null,
          audioFile: meta.audio_file || null,
          audioDuration: meta.duration || null,
          audioFilesize: meta.filesize || null,
          audioFilesizeRaw: meta.filesize_raw || null,
          episodeType: meta.episode_type || null,
          videoUrl: details.video_url || null,
          downloadLink: meta.download_link || null,
          playerLink: meta.player_link || null,
          ogDescription: yoast.og_description || null,
          ogImageUrl: yoast.og_image?.[0]?.url || null,
          canonicalUrl: yoast.canonical || null,
          status: post.status || "publish",
          sourceUrl: post.link || "",
          featuredMediaId: mediaExists ? featuredMediaId : null,
          seriesId: seriesExists ? seriesWpId : null,
        },
      });
      count++;
    }
    console.log(`  Created ${count} roundtable records`);
  }

  // ── Roundtable-Tag Joins ────────────────────────────────
  console.log("\nSeeding roundtable-tag relationships...");
  if (postsData) {
    let count = 0;
    for (const post of postsData) {
      const tagIds: number[] = post.tags || [];
      if (tagIds.length === 0) continue;

      const roundtable = await prisma.roundtable.findUnique({
        where: { wpId: post.id },
      });
      if (!roundtable) continue;

      for (const wpTagId of tagIds) {
        const tag = await prisma.tag.findUnique({ where: { wpId: wpTagId } });
        if (!tag) continue;

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
        count++;
      }
    }
    console.log(`  Created ${count} roundtable-tag relationships`);
  }

  // ── Roundtable-Participant Joins (from HTML scraping) ───
  console.log("\nSeeding roundtable-participant relationships...");
  const rtParticipants = readJson("roundtable_participants.json");
  if (rtParticipants) {
    let count = 0;
    let missing = 0;

    for (const [rtSlug, participants] of Object.entries(rtParticipants)) {
      const roundtable = await prisma.roundtable.findUnique({
        where: { slug: rtSlug },
      });
      if (!roundtable) {
        missing++;
        continue;
      }

      for (const p of participants as any[]) {
        const participant = await prisma.participant.findUnique({
          where: { slug: p.slug },
        });
        if (!participant) {
          missing++;
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
        count++;
      }
    }
    console.log(`  Created ${count} roundtable-participant relationships`);
    if (missing > 0) {
      console.log(`  Skipped ${missing} unresolved references`);
    }
  }

  // ── Site Config ─────────────────────────────────────────
  console.log("\nSeeding site config...");
  const configs = [
    { key: "site_name", value: "The Helix Center" },
    { key: "site_tagline", value: "An Unhurried Search for Wisdom" },
    { key: "site_url", value: "https://helixcenter.org" },
    { key: "media_url", value: "https://media.helixcenter.org" },
    {
      key: "social_facebook",
      value: "http://www.facebook.com/TheHelixCenter",
    },
    { key: "social_twitter", value: "https://twitter.com/thehelixcenter" },
    { key: "social_youtube", value: "http://www.youtube.com/helixcenter" },
    {
      key: "social_instagram",
      value: "https://www.instagram.com/helixcenter/",
    },
    {
      key: "social_apple_podcasts",
      value: "https://itunes.apple.com/us/podcast/the-helix-center/id1093679041",
    },
    {
      key: "rss_feed",
      value: "/feed/rss2/?post_type=roundtable",
    },
  ];
  for (const config of configs) {
    await prisma.siteConfig.upsert({
      where: { key: config.key },
      update: { value: config.value },
      create: config,
    });
  }
  console.log(`  Created ${configs.length} config entries`);

  console.log("\n=== Seeding Complete ===");
}

main()
  .catch((e) => {
    console.error("Seed error:", e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
