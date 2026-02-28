import Link from "next/link";
import Image from "next/image";

interface RoundtableCardProps {
  roundtable: {
    id: number;
    slug: string;
    title: string;
    excerpt: string;
    publishedAt: Date;
    eventDatetime: string | null;
    eventStatus: string | null;
    audioFile: string | null;
    featuredImage: { sourceUrl: string; altText: string } | null;
    participants: {
      participant: { slug: string; name: string };
    }[];
  };
}

export function RoundtableCard({ roundtable }: RoundtableCardProps) {
  return (
    <article className="border rounded-lg overflow-hidden hover:shadow-lg transition-shadow">
      <Link href={`/roundtables/${roundtable.slug}`}>
        {/* Image */}
        {roundtable.featuredImage && (
          <div className="relative h-48">
            <Image
              src={roundtable.featuredImage.sourceUrl}
              alt={roundtable.featuredImage.altText || roundtable.title}
              fill
              className="object-cover"
            />
          </div>
        )}

        <div className="p-4">
          {/* Date + Status + Audio badge */}
          <div className="flex flex-wrap items-center gap-2 text-sm text-gray-500 mb-2">
            <time>
              {roundtable.eventDatetime ||
                new Date(roundtable.publishedAt).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "short",
                  day: "numeric",
                })}
            </time>
            {roundtable.eventStatus && (
              <span
                className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                  roundtable.eventStatus === "Future Event"
                    ? "bg-green-100 text-green-800"
                    : "bg-gray-100 text-gray-600"
                }`}
              >
                {roundtable.eventStatus}
              </span>
            )}
            {roundtable.audioFile && (
              <span className="inline-flex items-center px-2 py-0.5 bg-helix-blue/10 text-helix-blue rounded text-xs">
                Audio
              </span>
            )}
          </div>

          {/* Title */}
          <h3 className="text-lg font-serif font-semibold mb-2">
            {roundtable.title}
          </h3>

          {/* Participants */}
          {roundtable.participants.length > 0 && (
            <p className="text-sm text-gray-600 line-clamp-1">
              {roundtable.participants
                .map((rp) => rp.participant.name)
                .join(", ")}
            </p>
          )}
        </div>
      </Link>
    </article>
  );
}
