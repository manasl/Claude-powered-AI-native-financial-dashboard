import { jwtVerify } from "jose";
import { NextResponse, type NextRequest } from "next/server";

const SESSION_COOKIE = "fin_session";

// Paths that don't require authentication
const PUBLIC_PATHS = ["/login", "/api/auth/verify-totp", "/api/auth/logout"];

function isPublic(pathname: string): boolean {
  return PUBLIC_PATHS.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (isPublic(pathname)) {
    return NextResponse.next();
  }

  const sessionToken = request.cookies.get(SESSION_COOKIE)?.value;
  const sessionSecret = process.env.SESSION_SECRET;

  if (!sessionSecret) {
    // Not configured yet — allow through so developer can see the app
    return NextResponse.next();
  }

  if (sessionToken) {
    try {
      const key = new TextEncoder().encode(sessionSecret);
      await jwtVerify(sessionToken, key);
      return NextResponse.next();
    } catch {
      // Expired or tampered token — fall through to redirect
    }
  }

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = "/login";
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
};
