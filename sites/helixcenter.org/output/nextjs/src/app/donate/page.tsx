import type { Metadata } from "next";
import { getPageBySlug } from "@/lib/queries";
import { DonateButton } from "@/components/pages/DonateButton";

export const metadata: Metadata = {
  title: "Donate",
  description: "Support The Helix Center's mission of fostering interdisciplinary dialogue.",
};

export default async function DonatePage() {
  const page = await getPageBySlug("donate");

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      <h1 className="text-4xl font-serif mb-8">Support The Helix Center</h1>

      {page && (
        <div
          className="wp-content mb-12"
          dangerouslySetInnerHTML={{ __html: page.content }}
        />
      )}

      <DonateButton />
    </div>
  );
}
