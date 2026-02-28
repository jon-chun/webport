import type { Metadata } from "next";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "The Helix Center — An Unhurried Search for Wisdom",
    template: "%s | The Helix Center",
  },
  description:
    "The Helix Center hosts interdisciplinary roundtable discussions exploring the connections between science, philosophy, and the arts.",
  openGraph: {
    siteName: "The Helix Center",
    type: "website",
    locale: "en_US",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen flex flex-col font-sans">
        <Header />
        <main className="flex-1">{children}</main>
        <Footer />
      </body>
    </html>
  );
}
