import { NextRequest, NextResponse } from "next/server";

const USER_ID_COOKIE = "geode.personalization.user";
const USER_ID_HEADER = "x-geode-user-id";

export function middleware(request: NextRequest): NextResponse {
  const existing = request.cookies.get(USER_ID_COOKIE)?.value;
  const userId = existing?.trim() || crypto.randomUUID();
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set(USER_ID_HEADER, userId);

  const response = NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });

  if (!existing) {
    response.cookies.set(USER_ID_COOKIE, userId, {
      httpOnly: false,
      sameSite: "lax",
      path: "/",
    });
  }

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};
