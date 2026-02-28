import type { Metadata } from "next";
import { getAllRoundtables } from "@/lib/queries";
import { RoundtableCard } from "@/components/roundtables/RoundtableCard";
import { Pagination } from "@/components/shared/Pagination";

export const metadata: Metadata = {
  title: "Roundtables",
  description:
    "Browse all Helix Center roundtable discussions — interdisciplinary conversations at the intersection of science, philosophy, and the arts.",
};

export default async function RoundtablesPage({
  searchParams,
}: {
  searchParams: { page?: string };
}) {
  const page = parseInt(searchParams.page || "1", 10);
  const { items, total, totalPages } = await getAllRoundtables(page, 12);

  return (
    <div className="max-w-6xl mx-auto px-4 py-12">
      <h1 className="text-4xl font-serif mb-2">Roundtables</h1>
      <p className="text-gray-600 mb-8">{total} roundtable discussions</p>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
        {items.map((rt) => (
          <RoundtableCard key={rt.id} roundtable={rt} />
        ))}
      </div>

      {totalPages > 1 && (
        <Pagination
          currentPage={page}
          totalPages={totalPages}
          basePath="/roundtables"
        />
      )}
    </div>
  );
}
