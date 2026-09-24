import { NextRequest, NextResponse } from "next/server";

import { proxyOrganizationRequest } from "@/lib/organization-proxy";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ membershipId: string }> },
): Promise<NextResponse> {
  const { membershipId } = await context.params;
  if (!/^[0-9a-f-]{36}$/i.test(membershipId)) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }
  return proxyOrganizationRequest(
    request,
    `/v1/organization-members/${membershipId}`,
    new Set(["PATCH", "DELETE"]),
  );
}

export const PATCH = proxy;
export const DELETE = proxy;
