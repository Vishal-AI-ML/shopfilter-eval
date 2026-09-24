import { NextRequest, NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/server-auth";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const methodsByAction: Record<string, ReadonlySet<string>> = {
  login: new Set(["POST"]),
  logout: new Set(["POST"]),
  me: new Set(["GET"]),
  register: new Set(["POST"]),
  "forgot-password": new Set(["POST"]),
  "reset-password": new Set(["POST"]),
};

function firstHeaderValue(value: string): string {
  return value.split(",", 1)[0].trim();
}

function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  const forwardedHost = request.headers.get("x-forwarded-host");
  const host = forwardedHost ?? request.headers.get("host");

  if (!origin || !host) {
    return false;
  }

  try {
    const originUrl = new URL(origin);
    const forwardedProto = request.headers.get("x-forwarded-proto");
    const expectedProtocol = forwardedProto
      ? `${firstHeaderValue(forwardedProto)}:`
      : request.nextUrl.protocol;

    return (
      originUrl.host === firstHeaderValue(host) &&
      originUrl.protocol === expectedProtocol
    );
  } catch {
    return false;
  }
}

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ action: string }> },
): Promise<NextResponse> {
  const { action } = await context.params;
  const allowedMethods = methodsByAction[action];

  if (!allowedMethods || !allowedMethods.has(request.method)) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }
  if (request.method !== "GET" && !sameOrigin(request)) {
    return NextResponse.json({ detail: "Cross-origin request rejected" }, { status: 403 });
  }

  const headers = new Headers();
  const cookie = request.headers.get("cookie");
  const contentType = request.headers.get("content-type");
  if (cookie) headers.set("cookie", cookie);
  if (contentType) headers.set("content-type", contentType);

  const upstream = await fetch(`${apiBaseUrl()}/v1/auth/${action}`, {
    method: request.method,
    headers,
    body: request.method === "GET" ? undefined : await request.arrayBuffer(),
    cache: "no-store",
    redirect: "manual",
  });

  const responseHeaders = new Headers();
  const upstreamContentType = upstream.headers.get("content-type");
  const setCookie = upstream.headers.get("set-cookie");
  if (upstreamContentType) responseHeaders.set("content-type", upstreamContentType);
  if (setCookie) responseHeaders.set("set-cookie", setCookie);
  responseHeaders.set("cache-control", "no-store");

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

export const GET = proxy;
export const POST = proxy;
