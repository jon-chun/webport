import Link from "next/link";
import Image from "next/image";

interface ParticipantCardProps {
  participant: {
    slug: string;
    name: string;
    professionalTitle: string;
    bio: string;
    featuredImage: { sourceUrl: string; altText: string } | null;
    roundtables: { roundtable: { id: number } }[];
  };
}

export function ParticipantCard({ participant }: ParticipantCardProps) {
  const bioText = participant.bio.replace(/<[^>]*>/g, "").slice(0, 120);

  return (
    <Link
      href={`/participants/${participant.slug}`}
      className="block border rounded-lg overflow-hidden hover:shadow-lg transition-shadow"
    >
      {/* Headshot */}
      {participant.featuredImage && (
        <div className="relative h-48">
          <Image
            src={participant.featuredImage.sourceUrl}
            alt={participant.name}
            fill
            className="object-cover object-top"
          />
        </div>
      )}

      <div className="p-4">
        <h3 className="font-serif font-semibold">{participant.name}</h3>
        {participant.professionalTitle && (
          <p className="text-sm text-gray-500 mt-0.5 line-clamp-1">
            {participant.professionalTitle}
          </p>
        )}
        {bioText && (
          <p className="text-sm text-gray-600 mt-1 line-clamp-2">{bioText}</p>
        )}
        {participant.roundtables.length > 0 && (
          <p className="text-xs text-gray-400 mt-2">
            {participant.roundtables.length} roundtable
            {participant.roundtables.length !== 1 ? "s" : ""}
          </p>
        )}
      </div>
    </Link>
  );
}
