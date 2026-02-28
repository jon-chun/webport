import type { Metadata } from "next";
import Link from "next/link";
import { getPageBySlug } from "@/lib/queries";

export const metadata: Metadata = {
  title: "About",
  description: "About The Helix Center — an interdisciplinary institute fostering dialogue between science, philosophy, and the arts.",
};

export default async function AboutPage() {
  const page = await getPageBySlug("about");

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      <h1 className="text-4xl font-serif mb-8">
        {page?.title || "About The Helix Center"}
      </h1>

      {page && (
        <div
          className="wp-content"
          dangerouslySetInnerHTML={{ __html: page.content }}
        />
      )}

      {/* Sub-pages */}
      {page?.children && page.children.length > 0 && (
        <nav className="mt-12 pt-8 border-t">
          <h2 className="text-2xl font-serif mb-4">Learn More</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {page.children.map((child) => (
              <Link
                key={child.id}
                href={`/about/${child.slug}`}
                className="block p-4 border rounded-lg hover:border-helix-blue hover:bg-gray-50 transition-colors"
              >
                <h3 className="font-semibold">{child.title}</h3>
              </Link>
            ))}
          </div>
        </nav>
      )}
    </div>
  );
}
