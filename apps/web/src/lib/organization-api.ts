import "server-only";

import { cookies } from "next/headers";

import type {
  CatalogSummary,
  CatalogVersionSummary,
  CatalogWithVersions,
} from "@/lib/catalog-types";
import { apiBaseUrl } from "@/lib/server-auth";
import type {
  OrganizationInvitation,
  OrganizationMember,
} from "@/lib/organization-types";
import type { ProjectSummary } from "@/lib/project-types";

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

export function getOrganizationProjects(
  organizationId: string,
): Promise<ProjectSummary[]> {
  return organizationRequest("/v1/projects", organizationId);
}

export async function getProjectCatalogs(
  organizationId: string,
  projectId: string,
): Promise<CatalogWithVersions[]> {
  const catalogs = await organizationRequest<CatalogSummary[]>(
    "/v1/catalogs",
    organizationId,
  );
  const scoped = catalogs.filter((catalog) => catalog.project_id === projectId);
  return Promise.all(
    scoped.map(async (catalog) => ({
      ...catalog,
      versions: await organizationRequest<CatalogVersionSummary[]>(
        `/v1/catalogs/${catalog.id}/versions`,
        organizationId,
      ),
    })),
  );
}
