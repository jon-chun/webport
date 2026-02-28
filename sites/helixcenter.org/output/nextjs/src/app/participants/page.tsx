import type { Metadata } from "next";
import { getAllParticipants } from "@/lib/queries";
import { ParticipantGrid } from "@/components/participants/ParticipantGrid";

export const metadata: Metadata = {
  title: "Participants",
  description:
    "Explore all Helix Center roundtable participants — scholars, scientists, artists, and thinkers from diverse disciplines.",
};

export default async function ParticipantsPage() {
  const participants = await getAllParticipants();

  return (
    <div className="max-w-6xl mx-auto px-4 py-12">
      <h1 className="text-4xl font-serif mb-2">Participants</h1>
      <p className="text-gray-600 mb-8">
        {participants.length} scholars, scientists, and thinkers
      </p>

      <ParticipantGrid participants={participants} />
    </div>
  );
}
