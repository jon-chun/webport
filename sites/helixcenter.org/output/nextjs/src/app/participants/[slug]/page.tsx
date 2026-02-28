import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import Image from "next/image";
import { getParticipantBySlug, getAllParticipantSlugs } from "@/lib/queries";
import { SEOJsonLd } from "@/components/shared/SEOJsonLd";

export async function generateStaticParams() {
  const slugs = await getAllParticipantSlugs();
  return slugs.map((s) => ({ slug: s.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const participant = await getParticipantBySlug(params.slug);
  if (!participant) return {};

  const description = participant.ogDescription
    || participant.bio.replace(/<[^>]*>/g, "").slice(0, 160);

  return {
    title: participant.name,
    description,
    openGraph: {
      title: participant.name,
      description,
      ...(participant.ogImageUrl && {
        images: [{ url: participant.ogImageUrl }],
      }),
    },
  };
}

export default async function ParticipantPage({
  params,
}: {
  params: { slug: string };
}) {
  const participant = await getParticipantBySlug(params.slug);
  if (!participant) notFound();

  const roundtables = participant.roundtables.map((rp) => rp.roundtable);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Person",
    name: participant.name,
    url: `${process.env.NEXT_PUBLIC_SITE_URL}/participants/${participant.slug}`,
    image: participant.featuredImage?.sourceUrl,
    description: participant.bio.replace(/<[^>]*>/g, "").slice(0, 300),
  };

  return (
    <article className="max-w-4xl mx-auto px-4 py-12">
      <SEOJsonLd data={jsonLd} />

      {/* Breadcrumbs */}
      <nav className="text-sm text-gray-500 mb-6">
        <Link href="/participants" className="hover:text-helix-blue">
          Participants
        </Link>
        <span className="mx-2">/</span>
        <span>{participant.name}</span>
      </nav>

      <div className="md:flex gap-8">
        {/* Headshot */}
        {participant.featuredImage && (
          <div className="flex-shrink-0 mb-6 md:mb-0">
            <div className="relative w-48 h-48 rounded-lg overflow-hidden">
              <Image
                src={participant.featuredImage.sourceUrl}
                alt={participant.name}
                fill
                className="object-cover"
                priority
              />
            </div>
          </div>
        )}

        {/* Name & Bio */}
        <div className="flex-1">
          <h1 className="text-4xl font-serif mb-2">{participant.name}</h1>
          {participant.professionalTitle && (
            <p className="text-lg text-gray-600 mb-6">
              {participant.professionalTitle}
            </p>
          )}
          {!participant.professionalTitle && <div className="mb-4" />}
          <div
            className="wp-content"
            dangerouslySetInnerHTML={{ __html: participant.bio }}
          />
        </div>
      </div>

      {/* Papers & Presentations */}
      {participant.hasPapers && participant.papersText && (
        <section className="mt-12">
          <h2 className="text-2xl font-serif mb-4">Papers &amp; Presentations</h2>
          <div
            className="wp-content prose"
            dangerouslySetInnerHTML={{ __html: participant.papersText }}
          />
        </section>
      )}

      {/* Roundtables */}
      {roundtables.length > 0 && (
        <section className="mt-12">
          <h2 className="text-2xl font-serif mb-6">Roundtable Discussions</h2>
          <div className="space-y-4">
            {roundtables.map((rt) => (
              <Link
                key={rt.id}
                href={`/roundtables/${rt.slug}`}
                className="block p-4 border rounded-lg hover:border-helix-blue hover:bg-gray-50 transition-colors"
              >
                <div className="flex items-center gap-4">
                  {rt.featuredImage && (
                    <div className="relative w-16 h-16 flex-shrink-0 rounded overflow-hidden">
                      <Image
                        src={rt.featuredImage.sourceUrl}
                        alt={rt.title}
                        fill
                        className="object-cover"
                      />
                    </div>
                  )}
                  <div>
                    <h3 className="font-semibold">{rt.title}</h3>
                    {rt.publishedAt && (
                      <p className="text-sm text-gray-500">
                        {new Date(rt.publishedAt).toLocaleDateString("en-US", {
                          year: "numeric",
                          month: "long",
                          day: "numeric",
                        })}
                      </p>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </article>
  );
}
