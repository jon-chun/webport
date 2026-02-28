interface SEOJsonLdProps {
  data: Record<string, unknown>;
}

export function SEOJsonLd({ data }: SEOJsonLdProps) {
  return (
    <script
      type="application/ld+json"
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data) }}
    />
  );
}
