import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { prisma } from "@/lib/prisma";
import { Breadcrumbs } from "@/components/shared/Breadcrumbs";

export async function generateStaticParams() {
  const aboutPage = await prisma.page.findUnique({ where: { slug: "about" } });
  if (!aboutPage) return [];
  const children = await prisma.page.findMany({
    where: { parentId: aboutPage.id },
    select: { slug: true },
  });
  return children.map((c) => ({ slug: c.slug }));
}

export async function generateMetadata({
  params,
}: {
  params: { slug: string };
}): Promise<Metadata> {
  const page = await prisma.page.findUnique({ where: { slug: params.slug } });
  if (!page) return {};
  return { title: page.title };
}

export default async function AboutSubPage({
  params,
}: {
  params: { slug: string };
}) {
  const page = await prisma.page.findUnique({
    where: { slug: params.slug },
    include: { parent: true },
  });
  if (!page) notFound();

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      <Breadcrumbs
        items={[
          { label: "About", href: "/about" },
          { label: page.title },
        ]}
      />

      <h1 className="text-4xl font-serif mb-8">{page.title}</h1>

      <div
        className="wp-content"
        dangerouslySetInnerHTML={{ __html: page.content }}
      />
    </div>
  );
}
