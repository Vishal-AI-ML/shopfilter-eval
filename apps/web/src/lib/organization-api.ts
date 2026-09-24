import "server-only";

import { cookies } from "next/headers";

import { apiBaseUrl } from "@/lib/server-auth";
import type {
  OrganizationInvitation,
  OrganizationMember,
} from "@/lib/organization-types";

async function organizationRequest<T>(
  path: string,
  organizationId: string,
): Promise<T> {
  const cookieStore = await cookies();
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    headers: {
      cookie: cookieStore.toString(),
      "x-organization-id": organizationId,
    },
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error(`Organization service returned HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export function getOrganizationMembers(
  organizationId: string,
): Promise<OrganizationMember[]> {
  return organizationRequest("/v1/organization-members", organizationId);
}

export function getOrganizationInvitations(
  organizationId: string,
): Promise<OrganizationInvitation[]> {
  return organizationRequest("/v1/organization-invitations", organizationId);
}
