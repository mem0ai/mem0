import { cookies } from "next/headers";
import { NextRequest, NextResponse } from "next/server";

const COOKIE_NAME = "mem0_refresh_token";
const COOKIE_OPTIONS = {
  httpOnly: true,
  secure: process.env.NODE_ENV === "production",
  sameSite: "lax" as const,
  path: "/",
  maxAge: 30 * 24 * 60 * 60, // 30 days
};

// POST — refresh the access token using the stored refresh token cookie
export async function POST() {
  const cookieStore = await cookies();
  const refreshToken = cookieStore.get(COOKIE_NAME)?.value;

  if (!refreshToken) {
    return NextResponse.json({ error: "No refresh token" }, { status: 401 });
  }

  const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  });

  if (!res.ok) {
    // Refresh token is invalid — clear cookie
    cookieStore.delete(COOKIE_NAME);
    return NextResponse.json({ error: "Refresh failed" }, { status: 401 });
  }

  const data = await res.json();

  // Update refresh token cookie
  cookieStore.set(COOKIE_NAME, data.refresh_token, COOKIE_OPTIONS);

  return NextResponse.json({ access_token: data.access_token });
}

// PUT — store a new refresh token (called after login)
export async function PUT(request: NextRequest) {
  const body = await request.json();
  const cookieStore = await cookies();

  if (!body.refresh_token) {
    return NextResponse.json({ error: "Missing refresh_token" }, { status: 400 });
  }

  cookieStore.set(COOKIE_NAME, body.refresh_token, COOKIE_OPTIONS);
  return NextResponse.json({ ok: true });
}

// DELETE — clear the refresh token (logout)
export async function DELETE() {
  const cookieStore = await cookies();
  cookieStore.delete(COOKIE_NAME);
  return NextResponse.json({ ok: true });
}
