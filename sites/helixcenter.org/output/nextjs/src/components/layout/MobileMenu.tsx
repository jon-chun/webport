"use client";

import Link from "next/link";

interface NavItem {
  label: string;
  href: string;
  children?: { label: string; href: string }[];
}

interface MobileMenuProps {
  open: boolean;
  onClose: () => void;
  items: NavItem[];
}

export function MobileMenu({ open, onClose, items }: MobileMenuProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 md:hidden">
      {/* Backdrop */}
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />

      {/* Panel */}
      <div className="absolute right-0 top-0 h-full w-72 bg-helix-dark text-white p-6">
        <button
          onClick={onClose}
          className="absolute top-4 right-4"
          aria-label="Close menu"
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
              d="M6 18L18 6M6 6l12 12"
            />
          </svg>
        </button>

        <nav className="mt-12 space-y-4">
          {items.map((item) => (
            <div key={item.label}>
              <Link
                href={item.href}
                onClick={onClose}
                className="block text-lg hover:text-helix-gold transition-colors"
              >
                {item.label}
              </Link>
              {item.children && (
                <div className="ml-4 mt-2 space-y-2">
                  {item.children.map((child) => (
                    <Link
                      key={child.href}
                      href={child.href}
                      onClick={onClose}
                      className="block text-sm text-gray-300 hover:text-helix-gold"
                    >
                      {child.label}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          ))}
          <Link
            href="/search"
            onClick={onClose}
            className="block text-lg hover:text-helix-gold transition-colors"
          >
            Search
          </Link>
        </nav>
      </div>
    </div>
  );
}
