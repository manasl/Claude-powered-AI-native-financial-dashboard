import { NextRequest, NextResponse } from "next/server";
import * as OTPAuth from "otpauth";
import { SignJWT } from "jose";

const SESSION_COOKIE = "fin_session";
const SESSION_EXPIRY_HOURS = 24;

export async function POST(request: NextRequest) {
  try {
    const { code } = await request.json() as { code?: string };

    if (!code || !/^\d{6}$/.test(code)) {
      return NextResponse.json({ error: "Invalid code format" }, { status: 400 });
    }

    const totpSecret = process.env.TOTP_SECRET;
    const sessionSecret = process.env.SESSION_SECRET;

    if (!totpSecret || !sessionSecret) {
      console.error("TOTP_SECRET or SESSION_SECRET not set in .env.local");
      return NextResponse.json({ error: "Server misconfigured" }, { status: 500 });
    }

    // Verify the TOTP code (window=1 accepts one period before/after for clock drift)
    const totp = new OTPAuth.TOTP({
      issuer: "FinancialDashboard",
      label: "Dashboard",
      algorithm: "SHA1",
      digits: 6,
      period: 30,
      secret: OTPAuth.Secret.fromBase32(totpSecret),
    });

    const delta = totp.validate({ token: code, window: 1 });

    if (delta === null) {
      return NextResponse.json({ error: "Invalid or expired code" }, { status: 401 });
    }

    // Issue a signed session JWT stored in an httpOnly cookie
    const key = new TextEncoder().encode(sessionSecret);
    const expiresAt = Math.floor(Date.now() / 1000) + SESSION_EXPIRY_HOURS * 3600;

    const sessionToken = await new SignJWT({ authenticated: true })
      .setProtectedHeader({ alg: "HS256" })
      .setIssuedAt()
      .setExpirationTime(expiresAt)
      .sign(key);

    const response = NextResponse.json({ ok: true });
    response.cookies.set(SESSION_COOKIE, sessionToken, {
      httpOnly: true,
      secure: false,        // localhost — set true in production
      sameSite: "lax",
      path: "/",
      maxAge: SESSION_EXPIRY_HOURS * 3600,
    });

    return response;
  } catch {
    return NextResponse.json({ error: "Internal error" }, { status: 500 });
  }
}
