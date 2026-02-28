"use client";

import { useState, useMemo } from "react";
import { ParticipantCard } from "./ParticipantCard";
import { AlphabetFilter } from "./AlphabetFilter";

interface ParticipantData {
  slug: string;
  name: string;
  professionalTitle: string;
  bio: string;
  featuredImage: { sourceUrl: string; altText: string } | null;
  roundtables: { roundtable: { id: number } }[];
}

interface ParticipantGridProps {
  participants: ParticipantData[];
}

function getLastNameInitial(name: string): string {
  const parts = name.trim().split(/\s+/);
  const lastName = parts[parts.length - 1] || "";
  return lastName.charAt(0).toUpperCase();
}

export function ParticipantGrid({ participants }: ParticipantGridProps) {
  const [activeLetter, setActiveLetter] = useState<string | null>(null);

  const availableLetters = useMemo(() => {
    const letters = new Set<string>();
    participants.forEach((p) => letters.add(getLastNameInitial(p.name)));
    return letters;
  }, [participants]);

  const filtered = useMemo(() => {
    if (!activeLetter) return participants;
    return participants.filter(
      (p) => getLastNameInitial(p.name) === activeLetter
    );
  }, [participants, activeLetter]);

  return (
    <div>
      <AlphabetFilter
        activeLetter={activeLetter}
        availableLetters={availableLetters}
        onSelect={setActiveLetter}
      />

      <p className="text-sm text-gray-500 mb-4">
        Showing {filtered.length} of {participants.length} participants
      </p>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
        {filtered.map((p) => (
          <ParticipantCard key={p.slug} participant={p} />
        ))}
      </div>
    </div>
  );
}
