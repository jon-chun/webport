import Link from "next/link";

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  basePath: string;
}

export function Pagination({
  currentPage,
  totalPages,
  basePath,
}: PaginationProps) {
  const pages = Array.from({ length: totalPages }, (_, i) => i + 1);

  // Show a window of pages around current
  const windowSize = 5;
  const start = Math.max(1, currentPage - Math.floor(windowSize / 2));
  const end = Math.min(totalPages, start + windowSize - 1);
  const visiblePages = pages.slice(start - 1, end);

  return (
    <nav className="flex items-center justify-center gap-2 mt-12" aria-label="Pagination">
      {currentPage > 1 && (
        <Link
          href={`${basePath}?page=${currentPage - 1}`}
          className="px-3 py-2 border rounded hover:bg-gray-50"
        >
          Previous
        </Link>
      )}

      {start > 1 && (
        <>
          <Link
            href={`${basePath}?page=1`}
            className="px-3 py-2 border rounded hover:bg-gray-50"
          >
            1
          </Link>
          {start > 2 && <span className="px-2 text-gray-400">...</span>}
        </>
      )}

      {visiblePages.map((page) => (
        <Link
          key={page}
          href={`${basePath}?page=${page}`}
          className={`px-3 py-2 border rounded ${
            page === currentPage
              ? "bg-helix-blue text-white border-helix-blue"
              : "hover:bg-gray-50"
          }`}
        >
          {page}
        </Link>
      ))}

      {end < totalPages && (
        <>
          {end < totalPages - 1 && (
            <span className="px-2 text-gray-400">...</span>
          )}
          <Link
            href={`${basePath}?page=${totalPages}`}
            className="px-3 py-2 border rounded hover:bg-gray-50"
          >
            {totalPages}
          </Link>
        </>
      )}

      {currentPage < totalPages && (
        <Link
          href={`${basePath}?page=${currentPage + 1}`}
          className="px-3 py-2 border rounded hover:bg-gray-50"
        >
          Next
        </Link>
      )}
    </nav>
  );
}
