import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { RoundtableCard } from "@/components/roundtables/RoundtableCard";

export default async function HomePage() {
  const roundtables = await prisma.roundtable.findMany({
    where: { status: "publish" },
    orderBy: { publishedAt: "desc" },
    take: 6,
    include: {
      featuredImage: true,
      participants: {
        include: { participant: true },
      },
    },
  });

  return (
    <div>
      {/* Hero Section */}
      <section className="bg-helix-dark text-white py-20 px-4">
        <div className="max-w-4xl mx-auto text-center">
          <h1 className="text-4xl md:text-5xl font-serif mb-4">
            The Helix Center
          </h1>
          <p className="text-xl text-helix-cream/80 font-serif italic">
            An Unhurried Search for Wisdom
          </p>
        </div>
      </section>

      {/* Recent Roundtables */}
      <section className="max-w-6xl mx-auto px-4 py-16">
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-3xl font-serif">Recent Roundtables</h2>
          <Link
            href="/roundtables"
            className="text-helix-blue hover:text-helix-accent transition-colors"
          >
            View all &rarr;
          </Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {roundtables.map((rt) => (
            <RoundtableCard key={rt.id} roundtable={rt} />
          ))}
        </div>
      </section>
    </div>
  );
}
