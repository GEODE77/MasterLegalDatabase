import { NextRequest, NextResponse } from "next/server";

const USER_ID_COOKIE = "geode.personalization.user";
const USER_ID_HEADER = "x-geode-user-id";
const MANAGER_COOKIE = "geode.manager.session";

const MANAGER_ROUTE_PREFIXES = ["/manager", "/debug", "/internal", "/settings"];
const MANAGER_API_PREFIXES = ["/api/product"];

export function middleware(request: NextRequest): NextResponse {
  const pathname = request.nextUrl.pathname;

  if (pathname === "/app" || pathname.startsWith("/app/")) {
    return NextResponse.redirect(managerRedirectUrl(request));
  }

  if (requiresManagerVerification(pathname) && pathname !== "/manager/verify") {
    const verified = Boolean(request.cookies.get(MANAGER_COOKIE)?.value);

    if (!verified) {
      if (pathname.startsWith("/api/")) {
        return NextResponse.json({ error: "Manager verification required." }, { status: 401 });
      }

      const verifyUrl = new URL("/manager/verify", request.url);
      verifyUrl.searchParams.set("next", `${pathname}${request.nextUrl.search}`);
      return NextResponse.redirect(verifyUrl);
    }
  }

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

function managerRedirectUrl(request: NextRequest): URL {
  const url = request.nextUrl.clone();
  const pathname = request.nextUrl.pathname;
  const managerPath = pathname === "/app" ? "/manager/dashboard" : pathname.replace(/^\/app/, "/manager");

  url.pathname = supportedManagerPath(managerPath);
  return url;
}

function supportedManagerPath(pathname: string): string {
  const supported = new Set([
    "/manager/dashboard",
    "/manager/sources",
    "/manager/review-queue",
    "/manager/explore",
    "/manager/relationships",
    "/manager/timeline",
    "/manager/ask",
    "/manager/publish",
  ]);

  return supported.has(pathname) ? pathname : "/manager/dashboard";
}

function requiresManagerVerification(pathname: string): boolean {
  return (
    MANAGER_ROUTE_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)) ||
    MANAGER_API_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`))
  );
}
