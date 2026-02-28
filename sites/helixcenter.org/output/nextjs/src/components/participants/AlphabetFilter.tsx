"use client";

const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

interface AlphabetFilterProps {
  activeLetter: string | null;
  availableLetters: Set<string>;
  onSelect: (letter: string | null) => void;
}

export function AlphabetFilter({
  activeLetter,
  availableLetters,
  onSelect,
}: AlphabetFilterProps) {
  return (
    <div className="flex flex-wrap gap-1 mb-8">
      <button
        onClick={() => onSelect(null)}
        className={`px-3 py-1 text-sm rounded ${
          activeLetter === null
            ? "bg-helix-blue text-white"
            : "bg-gray-100 text-gray-700 hover:bg-gray-200"
        }`}
      >
        All
      </button>
      {LETTERS.map((letter) => (
        <button
          key={letter}
          onClick={() => onSelect(letter)}
          disabled={!availableLetters.has(letter)}
          className={`px-3 py-1 text-sm rounded ${
            activeLetter === letter
              ? "bg-helix-blue text-white"
              : availableLetters.has(letter)
                ? "bg-gray-100 text-gray-700 hover:bg-gray-200"
                : "bg-gray-50 text-gray-300 cursor-not-allowed"
          }`}
        >
          {letter}
        </button>
      ))}
    </div>
  );
}
