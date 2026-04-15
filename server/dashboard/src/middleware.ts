import { NextRequest, NextResponse } from "next/server";
import { AUTH_ENDPOINTS } from "@/utils/api-endpoints";
import { getServerApiUrl } from "@/lib/server-api-url";

const PUBLIC_PATHS = [
  "/_next",
  "/api/auth",
  "/api/health",
  "/fonts",
  "/favicon",
];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  const hasRefreshToken = request.cookies.has("mem0_refresh_token");

  if (pathname === "/" || pathname === "/login" || pathname === "/setup") {
    try {
      const res = await fetch(
        `${getServerApiUrl()}${AUTH_ENDPOINTS.SETUP_STATUS}`,
      );
      if (res.ok) {
        const { needsSetup } = await res.json();

        if (needsSetup && pathname !== "/setup") {
          return NextResponse.redirect(new URL("/setup", request.url));
        }
        if (!needsSetup && pathname === "/setup") {
          return NextResponse.redirect(new URL("/login", request.url));
        }
      }
    } catch {
      // API unreachable — fall through to default behavior
    }
  }

  if (pathname === "/login" || pathname === "/setup") {
    return NextResponse.next();
  }

  if (pathname === "/") {
    return NextResponse.redirect(
      new URL(hasRefreshToken ? "/dashboard/requests" : "/login", request.url),
    );
  }

  if (pathname === "/dashboard" || pathname === "/dashboard/") {
    return NextResponse.redirect(new URL("/dashboard/requests", request.url));
  }

  if (!hasRefreshToken) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|fonts|images|icons).*)"],
};
