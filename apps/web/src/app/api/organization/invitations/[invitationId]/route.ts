import { NextRequest, NextResponse } from "next/server";

import { proxyOrganizationRequest } from "@/lib/organization-proxy";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ invitationId: string }> },
): Promise<NextResponse> {
  const { invitationId } = await context.params;
  if (!/^[0-9a-f-]{36}$/i.test(invitationId)) {
    return NextResponse.json({ detail: "Not found" }, { status: 404 });
  }
  return proxyOrganizationRequest(
    request,
    `/v1/organization-invitations/${invitationId}`,
    new Set(["DELETE"]),
  );
}

export const DELETE = proxy;
