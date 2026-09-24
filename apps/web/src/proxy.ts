import { NextRequest, NextResponse } from "next/server";

const DEFAULT_API_URL = "http://localhost:8000";

function loginRedirect(request: NextRequest): NextResponse {
  const url = request.nextUrl.clone();
  url.pathname = "/login";
  url.search = "";
  return NextResponse.redirect(url);
}

export async function proxy(request: NextRequest): Promise<NextResponse> {
  const cookie = request.headers.get("cookie");
  if (!cookie) {
    return loginRedirect(request);
  }

  try {
    const apiUrl = new URL(
      "/v1/auth/me",
      process.env.SHOPFILTER_API_INTERNAL_URL ?? DEFAULT_API_URL,
    );
    const response = await fetch(apiUrl, {
      headers: { cookie },
      cache: "no-store",
    });
    if (!response.ok) {
      return loginRedirect(request);
    }
  } catch {
    return loginRedirect(request);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
