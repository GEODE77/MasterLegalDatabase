import { createHash, timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

const MANAGER_COOKIE = "geode.manager.verified";
const DEV_ACCESS_CODE = "local-manager-preview";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = (await request.json().catch(() => null)) as { code?: unknown } | null;
  const code = typeof payload?.code === "string" ? payload.code.trim() : "";
  const expectedCode = process.env.GEODE_MANAGER_ACCESS_CODE?.trim();

  if (!expectedCode && process.env.NODE_ENV === "production") {
    return NextResponse.json({ error: "Manager verification is not configured." }, { status: 503 });
  }

  const validCode = expectedCode || DEV_ACCESS_CODE;
  if (!code || !isSameSecret(code, validCode)) {
    return NextResponse.json({ error: "The manager access code was not accepted." }, { status: 401 });
  }

  const response = NextResponse.json({ ok: true });
  response.cookies.set(MANAGER_COOKIE, "1", {
    httpOnly: true,
    maxAge: 60 * 60 * 8,
    path: "/",
    sameSite: "lax",
    secure: request.nextUrl.protocol === "https:",
  });
  return response;
}

function isSameSecret(value: string, expected: string): boolean {
  const valueHash = createHash("sha256").update(value).digest();
  const expectedHash = createHash("sha256").update(expected).digest();
  return timingSafeEqual(valueHash, expectedHash);
}
