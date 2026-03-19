import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Google OAuth callback is no longer used — auth is handled via TOTP.
// This route redirects to home to avoid broken links if it's ever hit.
export async function GET(request: NextRequest) {
  const { origin } = new URL(request.url);
  return NextResponse.redirect(`${origin}/`);
}
