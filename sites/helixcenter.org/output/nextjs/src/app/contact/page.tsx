import type { Metadata } from "next";
import { getPageBySlug } from "@/lib/queries";
import { ContactForm } from "@/components/pages/ContactForm";

export const metadata: Metadata = {
  title: "Contact",
  description: "Contact The Helix Center — located at 247 East 82nd Street, New York, NY 10028.",
};

export default async function ContactPage() {
  const page = await getPageBySlug("contact");

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      <h1 className="text-4xl font-serif mb-8">Contact</h1>

      {page && (
        <div
          className="wp-content mb-12"
          dangerouslySetInnerHTML={{ __html: page.content }}
        />
      )}

      <ContactForm />
    </div>
  );
}
