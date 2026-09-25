import { NextRequest, NextResponse } from "next/server";

import { proxyOrganizationRequest } from "@/lib/organization-proxy";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

async function proxy(request: NextRequest): Promise<NextResponse> {
  return proxyOrganizationRequest(
    request,
    "/v1/catalogs",
    new Set(["GET"]),
  );
}

export const GET = proxy;
