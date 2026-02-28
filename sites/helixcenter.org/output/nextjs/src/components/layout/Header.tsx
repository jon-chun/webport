"use client";

import { useState } from "react";
import Link from "next/link";
import { MobileMenu } from "./MobileMenu";

const navItems = [
  { label: "Roundtables", href: "/roundtables" },
  { label: "Participants", href: "/participants" },
  {
    label: "About",
    href: "/about",
    children: [
      { label: "About", href: "/about" },
      { label: "Board of Directors", href: "/about/board-of-directors" },
      { label: "Executive Committee", href: "/about/executive-committee" },
    ],
  },
  { label: "Contact", href: "/contact" },
  { label: "Donate", href: "/donate" },
];

export function Header() {
  const [mobileOpen, setMobileOpen] = useState(false);
  const [dropdownOpen, setDropdownOpen] = useState(false);

  return (
    <header className="bg-helix-dark text-white">
      <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
        {/* Logo */}
        <Link href="/" className="text-xl font-serif tracking-wide">
          The Helix Center
        </Link>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-6">
          {navItems.map((item) =>
            item.children ? (
              <div
                key={item.label}
                className="relative"
                onMouseEnter={() => setDropdownOpen(true)}
                onMouseLeave={() => setDropdownOpen(false)}
              >
                <button className="hover:text-helix-gold transition-colors">
                  {item.label}
                </button>
                {dropdownOpen && (
                  <div className="absolute top-full left-0 mt-1 bg-white text-gray-900 rounded shadow-lg py-2 min-w-48 z-50">
                    {item.children.map((child) => (
                      <Link
                        key={child.href}
                        href={child.href}
                        className="block px-4 py-2 hover:bg-gray-100"
                      >
                        {child.label}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <Link
                key={item.href}
                href={item.href}
                className="hover:text-helix-gold transition-colors"
              >
                {item.label}
              </Link>
            )
          )}
          <Link
            href="/search"
            className="hover:text-helix-gold transition-colors"
            aria-label="Search"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-5 w-5"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
          </Link>
        </nav>

        {/* Mobile hamburger */}
        <button
          className="md:hidden p-2"
          onClick={() => setMobileOpen(true)}
          aria-label="Open menu"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-6 w-6"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M4 6h16M4 12h16M4 18h16"
            />
          </svg>
        </button>
      </div>

      <MobileMenu
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
        items={navItems}
      />
    </header>
  );
}
