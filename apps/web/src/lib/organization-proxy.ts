import { NextRequest, NextResponse } from "next/server";

import { apiBaseUrl } from "@/lib/server-auth";

function firstHeaderValue(value: string): string {
  return value.split(",", 1)[0].trim();
}

function sameOrigin(request: NextRequest): boolean {
  const origin = request.headers.get("origin");
  const forwardedHost = request.headers.get("x-forwarded-host");
  const host = forwardedHost ?? request.headers.get("host");
  if (!origin || !host) return false;

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

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export async function proxyOrganizationRequest(
  request: NextRequest,
  path: string,
  allowedMethods: ReadonlySet<string>,
): Promise<NextResponse> {
  if (!allowedMethods.has(request.method)) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }
  if (request.method !== "GET" && !sameOrigin(request)) {
    return NextResponse.json(
      { detail: "Cross-origin request rejected" },
      { status: 403 },
    );
  }

  const organizationId = request.headers.get("x-organization-id");
  if (!organizationId || !UUID_PATTERN.test(organizationId)) {
    return NextResponse.json(
      { detail: "Organization context required" },
      { status: 400 },
    );
  }

  const headers = new Headers({ "x-organization-id": organizationId });
  const cookie = request.headers.get("cookie");
  const contentType = request.headers.get("content-type");
  if (cookie) headers.set("cookie", cookie);
  if (contentType) headers.set("content-type", contentType);

  const upstream = await fetch(`${apiBaseUrl()}${path}`, {
    method: request.method,
    headers,
    body: ["POST", "PATCH"].includes(request.method)
      ? await request.arrayBuffer()
      : undefined,
    cache: "no-store",
    redirect: "manual",
  });

  const responseHeaders = new Headers({ "cache-control": "no-store" });
  const upstreamContentType = upstream.headers.get("content-type");
  if (upstreamContentType) {
    responseHeaders.set("content-type", upstreamContentType);
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}
