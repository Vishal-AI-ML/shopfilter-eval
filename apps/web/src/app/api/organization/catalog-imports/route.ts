import { NextRequest, NextResponse } from "next/server";

import { proxyOrganizationRequest } from "@/lib/organization-proxy";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const MAX_CATALOG_IMPORT_BYTES = 25 * 1024 * 1024;

async function proxy(request: NextRequest): Promise<NextResponse> {
  return proxyOrganizationRequest(
    request,
    "/v1/catalog-imports",
    new Set(["POST"]),
    MAX_CATALOG_IMPORT_BYTES,
  );
}

export const POST = proxy;
