import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { getRoundtableBySlug, getAllRoundtableSlugs } from "@/lib/queries";
import { AudioPlayer } from "@/components/roundtables/AudioPlayer";
import { ParticipantChips } from "@/components/roundtables/ParticipantChips";
import { SEOJsonLd } from "@/components/shared/SEOJsonLd";

export async function generateStaticParams() {
  const slugs = await getAllRoundtableSlugs();
  return slugs.map((s) => ({ slug: s.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const roundtable = await getRoundtableBySlug(params.slug);
  if (!roundtable) return {};

  const description = roundtable.ogDescription
    || roundtable.excerpt.replace(/<[^>]*>/g, "").slice(0, 160);

  return {
    title: roundtable.title,
    description,
    openGraph: {
      title: roundtable.title,
      description,
      ...(roundtable.ogImageUrl && {
        images: [{ url: roundtable.ogImageUrl }],
      }),
    },
  };
}

export default async function RoundtablePage({
  params,
}: {
  params: { slug: string };
}) {
  const roundtable = await getRoundtableBySlug(params.slug);
  if (!roundtable) notFound();

  const participants = roundtable.participants.map((rp) => rp.participant);
  const tags = roundtable.tags.map((rt) => rt.tag);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Event",
    name: roundtable.title,
    description: roundtable.excerpt.replace(/<[^>]*>/g, ""),
    startDate: roundtable.dateRecorded?.toISOString() || roundtable.publishedAt.toISOString(),
    location: {
      "@type": "Place",
      name: "The Helix Center",
      address: "247 East 82nd Street, New York, NY 10028",
    },
    performer: participants.map((p) => ({
      "@type": "Person",
      name: p.name,
      url: `${process.env.NEXT_PUBLIC_SITE_URL}/participants/${p.slug}`,
    })),
  };

  return (
    <article className="max-w-4xl mx-auto px-4 py-12">
      <SEOJsonLd data={jsonLd} />

      {/* Breadcrumbs */}
      <nav className="text-sm text-gray-500 mb-6">
        <Link href="/roundtables" className="hover:text-helix-blue">
          Roundtables
        </Link>
        <span className="mx-2">/</span>
        <span>{roundtable.title}</span>
      </nav>

      {/* Featured Image */}
      {roundtable.featuredImage && (
        <div className="relative w-full h-64 md:h-96 mb-8 rounded-lg overflow-hidden">
          <Image
            src={roundtable.featuredImage.sourceUrl}
            alt={roundtable.featuredImage.altText || roundtable.title}
            fill
            className="object-cover"
            priority
          />
        </div>
      )}

      {/* Title & Event Info */}
      <h1 className="text-4xl font-serif mb-3">{roundtable.title}</h1>
      <div className="flex flex-wrap items-center gap-3 mb-6">
        {roundtable.eventDatetime && (
          <p className="text-gray-600">
            {roundtable.eventDatetime}
          </p>
        )}
        {!roundtable.eventDatetime && roundtable.dateRecorded && (
          <p className="text-gray-600">
            {new Date(roundtable.dateRecorded).toLocaleDateString("en-US", {
              weekday: "long",
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </p>
        )}
        {roundtable.eventStatus && (
          <span
            className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
              roundtable.eventStatus === "Future Event"
                ? "bg-green-100 text-green-800"
                : "bg-gray-100 text-gray-700"
            }`}
          >
            {roundtable.eventStatus}
          </span>
        )}
      </div>

      {/* Audio Player */}
      {roundtable.audioFile && (
        <AudioPlayer
          src={roundtable.audioFile}
          duration={roundtable.audioDuration || undefined}
          title={roundtable.title}
        />
      )}

      {/* Video Embed */}
      {roundtable.videoUrl && (
        <div className="my-8">
          <div className="relative w-full aspect-video rounded-lg overflow-hidden">
            <iframe
              src={roundtable.videoUrl}
              title={roundtable.title}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
              className="absolute inset-0 w-full h-full"
            />
          </div>
        </div>
      )}

      {/* Participants */}
      {participants.length > 0 && (
        <section className="my-8">
          <h2 className="text-xl font-serif mb-4">Participants</h2>
          <ParticipantChips participants={participants} />
        </section>
      )}

      {/* Content */}
      <div
        className="wp-content mt-8"
        dangerouslySetInnerHTML={{ __html: roundtable.content }}
      />

      {/* Tags */}
      {tags.length > 0 && (
        <div className="mt-8 pt-6 border-t">
          <h3 className="text-sm font-semibold text-gray-500 uppercase mb-3">
            Topics
          </h3>
          <div className="flex flex-wrap gap-2">
            {tags.map((tag) => (
              <span
                key={tag.id}
                className="px-3 py-1 bg-gray-100 text-gray-700 text-sm rounded-full"
              >
                {tag.name}
              </span>
            ))}
          </div>
        </div>
      )}
    </article>
  );
}
