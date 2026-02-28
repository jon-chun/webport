import { NextRequest, NextResponse } from "next/server";
import { search } from "@/lib/queries";

export async function GET(request: NextRequest) {
  const query = request.nextUrl.searchParams.get("q");

  if (!query || query.length < 2) {
    return NextResponse.json({ roundtables: [], participants: [] });
  }

  // Sanitize: limit length, strip HTML
  const sanitized = query.slice(0, 100).replace(/<[^>]*>/g, "");

  const results = await search(sanitized);
  return NextResponse.json(results);
}
