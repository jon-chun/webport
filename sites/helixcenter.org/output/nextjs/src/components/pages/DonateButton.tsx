export function DonateButton() {
  return (
    <div className="text-center py-8">
      <a
        href="https://www.helixcenter.org/donate/"
        target="_blank"
        rel="noopener noreferrer"
        className="inline-block px-8 py-4 bg-helix-accent text-white text-lg font-semibold rounded-lg hover:bg-helix-blue transition-colors"
      >
        Make a Donation
      </a>
      <p className="text-sm text-gray-500 mt-4">
        The Helix Center is a 501(c)(3) non-profit organization. Your
        contribution is tax-deductible.
      </p>
    </div>
  );
}
