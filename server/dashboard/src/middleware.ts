import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/login", "/setup", "/_next", "/api/auth", "/fonts", "/favicon"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Allow public paths
  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // Check for refresh token cookie (presence = likely authenticated)
  const hasRefreshToken = request.cookies.has("mem0_refresh_token");

  // Root redirect
  if (pathname === "/") {
    if (hasRefreshToken) {
      return NextResponse.redirect(new URL("/dashboard/", request.url));
    }
    return NextResponse.redirect(new URL("/login", request.url));
  }

  // Protected routes — redirect to login if no token
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
