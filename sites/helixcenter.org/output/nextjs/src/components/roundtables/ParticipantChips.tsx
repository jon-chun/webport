import Link from "next/link";
import Image from "next/image";

interface Participant {
  slug: string;
  name: string;
  featuredImage?: { sourceUrl: string; altText: string } | null;
}

interface ParticipantChipsProps {
  participants: Participant[];
}

export function ParticipantChips({ participants }: ParticipantChipsProps) {
  return (
    <div className="flex flex-wrap gap-3">
      {participants.map((p) => (
        <Link
          key={p.slug}
          href={`/participants/${p.slug}`}
          className="flex items-center gap-2 px-3 py-2 bg-gray-50 border rounded-full hover:bg-gray-100 hover:border-helix-blue transition-colors"
        >
          {p.featuredImage && (
            <div className="relative w-8 h-8 rounded-full overflow-hidden flex-shrink-0">
              <Image
                src={p.featuredImage.sourceUrl}
                alt={p.name}
                fill
                className="object-cover"
              />
            </div>
          )}
          <span className="text-sm font-medium">{p.name}</span>
        </Link>
      ))}
    </div>
  );
}
