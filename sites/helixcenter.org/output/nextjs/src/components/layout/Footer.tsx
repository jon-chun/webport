import Link from "next/link";
import { SocialLinks } from "../shared/SocialLinks";

export function Footer() {
  return (
    <footer className="bg-helix-dark text-white py-12">
      <div className="max-w-6xl mx-auto px-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {/* About */}
          <div>
            <h3 className="font-serif text-lg mb-3">The Helix Center</h3>
            <p className="text-gray-400 text-sm italic">
              An Unhurried Search for Wisdom
            </p>
            <p className="text-gray-400 text-sm mt-2">
              247 East 82nd Street
              <br />
              New York, NY 10028
            </p>
          </div>

          {/* Links */}
          <div>
            <h3 className="font-serif text-lg mb-3">Explore</h3>
            <nav className="space-y-2 text-sm">
              <Link
                href="/roundtables"
                className="block text-gray-400 hover:text-white"
              >
                Roundtables
              </Link>
              <Link
                href="/participants"
                className="block text-gray-400 hover:text-white"
              >
                Participants
              </Link>
              <Link
                href="/about"
                className="block text-gray-400 hover:text-white"
              >
                About
              </Link>
              <Link
                href="/contact"
                className="block text-gray-400 hover:text-white"
              >
                Contact
              </Link>
              <Link
                href="/donate"
                className="block text-gray-400 hover:text-white"
              >
                Donate
              </Link>
            </nav>
          </div>

          {/* Social */}
          <div>
            <h3 className="font-serif text-lg mb-3">Connect</h3>
            <SocialLinks />
          </div>
        </div>

        <div className="mt-8 pt-8 border-t border-gray-700 text-center text-gray-500 text-sm">
          &copy; {new Date().getFullYear()} The Helix Center. All rights
          reserved.
        </div>
      </div>
    </footer>
  );
}
