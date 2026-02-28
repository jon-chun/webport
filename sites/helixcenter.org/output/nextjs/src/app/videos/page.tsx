import type { Metadata } from "next";
import { getPageBySlug } from "@/lib/queries";

export const metadata: Metadata = {
  title: "Videos",
};

export default async function VideosPage() {
  const page = await getPageBySlug("videos");

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      <h1 className="text-4xl font-serif mb-8">{page?.title || "Videos"}</h1>
      {page && (
        <div
          className="wp-content"
          dangerouslySetInnerHTML={{ __html: page.content }}
        />
      )}
    </div>
  );
}
