"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

interface SearchResult {
  type: "roundtable" | "participant";
  slug: string;
  title: string;
  excerpt: string;
}

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{
    roundtables: SearchResult[];
    participants: SearchResult[];
  }>({ roundtables: [], participants: [] });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (query.length < 2) {
      setResults({ roundtables: [], participants: [] });
      return;
    }

    const timeout = setTimeout(async () => {
      setLoading(true);
      try {
        const res = await fetch(
          `/api/search?q=${encodeURIComponent(query)}`
        );
        const data = await res.json();
        setResults(data);
      } catch {
        // Silently handle errors
      } finally {
        setLoading(false);
      }
    }, 300);

    return () => clearTimeout(timeout);
  }, [query]);

  const hasResults =
    results.roundtables.length > 0 || results.participants.length > 0;

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      <h1 className="text-4xl font-serif mb-8">Search</h1>

      <input
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search roundtables and participants..."
        className="w-full px-4 py-3 border rounded-lg text-lg focus:outline-none focus:ring-2 focus:ring-helix-blue"
        autoFocus
      />

      {loading && <p className="mt-4 text-gray-500">Searching...</p>}

      {!loading && query.length >= 2 && !hasResults && (
        <p className="mt-4 text-gray-500">No results found for "{query}"</p>
      )}

      {results.roundtables.length > 0 && (
        <section className="mt-8">
          <h2 className="text-xl font-serif mb-4">Roundtables</h2>
          <div className="space-y-3">
            {results.roundtables.map((r) => (
              <Link
                key={r.slug}
                href={`/roundtables/${r.slug}`}
                className="block p-4 border rounded-lg hover:bg-gray-50"
              >
                <h3 className="font-semibold">{r.title}</h3>
                <p className="text-sm text-gray-600 mt-1">{r.excerpt}</p>
              </Link>
            ))}
          </div>
        </section>
      )}

      {results.participants.length > 0 && (
        <section className="mt-8">
          <h2 className="text-xl font-serif mb-4">Participants</h2>
          <div className="space-y-3">
            {results.participants.map((p) => (
              <Link
                key={p.slug}
                href={`/participants/${p.slug}`}
                className="block p-4 border rounded-lg hover:bg-gray-50"
              >
                <h3 className="font-semibold">{p.title}</h3>
                <p className="text-sm text-gray-600 mt-1">{p.excerpt}</p>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
