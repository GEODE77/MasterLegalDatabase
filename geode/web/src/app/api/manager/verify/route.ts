import { NextRequest, NextResponse } from "next/server";

import { createManagerSession, verifyManagerInvite } from "@/lib/manager/store";

export const dynamic = "force-dynamic";

const MANAGER_COOKIE = "geode.manager.session";

export async function POST(request: NextRequest): Promise<NextResponse> {
  const payload = (await request.json().catch(() => null)) as { code?: unknown; email?: unknown } | null;
  const code = typeof payload?.code === "string" ? payload.code.trim() : "";
  const email = typeof payload?.email === "string" ? payload.email.trim() : "";

  const manager = verifyManagerInvite(email, code);
  if (!manager) {
    return NextResponse.json({ error: "The manager invite was not accepted." }, { status: 401 });
  }

  let sessionValue = "";
  try {
    sessionValue = createManagerSession(manager);
  } catch {
    return NextResponse.json({ error: "Manager sessions are not configured." }, { status: 503 });
  }

  const response = NextResponse.json({
    manager: {
      email: manager.email,
      id: manager.id,
      name: manager.name,
      role: manager.role,
    },
    ok: true,
  });
  response.cookies.set(MANAGER_COOKIE, sessionValue, {
    httpOnly: true,
    maxAge: 60 * 60 * 8,
    path: "/",
    sameSite: "lax",
    secure: request.nextUrl.protocol === "https:",
  });
  return response;
}
