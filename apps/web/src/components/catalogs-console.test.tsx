import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const navigation = vi.hoisted(() => ({ refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => navigation }));

import { CatalogsConsole } from "@/components/catalogs-console";
import type { CatalogWithVersions } from "@/lib/catalog-types";
import type { ProjectSummary } from "@/lib/project-types";

const organizationId = "e5150000-0000-4000-8000-000000000001";
const project: ProjectSummary = {
  id: "e5150000-0000-4000-8000-000000000002",
  organization_id: organizationId,
  name: "Search Quality",
  slug: "search-quality",
  created_at: "2026-09-24T12:00:00Z",
};
const catalog: CatalogWithVersions = {
  id: "11111111-1111-4111-8111-111111111111",
  organization_id: organizationId,
  project_id: project.id,
  external_id: "esci-catalog",
  name: "ESCI Catalog",
  created_at: "2026-09-24T12:00:00Z",
  versions: [
    {
      id: "22222222-2222-4222-8222-222222222222",
      organization_id: organizationId,
      catalog_id: "11111111-1111-4111-8111-111111111111",
      version: "v1",
      status: "PUBLISHED",
      content_hash: "a".repeat(64),
      artifact_hash: "b".repeat(64),
      item_count: 10001,
      provenance: { hash_algorithm: "sha256" },
      created_at: "2026-09-24T12:00:00Z",
    },
  ],
};

afterEach(() => {
  vi.unstubAllGlobals();
  navigation.refresh.mockReset();
});

describe("CatalogsConsole", () => {
  it("renders immutable version and quality evidence", () => {
    render(
      <CatalogsConsole
        organizationId={organizationId}
        project={project}
        currentRole="OWNER"
        catalogs={[catalog]}
      />,
    );

    expect(screen.getByText("ESCI Catalog")).toBeInTheDocument();
    expect(screen.getByText("10,001")).toBeInTheDocument();
    expect(screen.getByText("Schema validated")).toBeInTheDocument();
    expect(screen.getByText("Duplicate IDs rejected")).toBeInTheDocument();
    expect(screen.getByText("Immutable hash locked")).toBeInTheDocument();
  });

  it("imports a selected JSON artifact through the size-limited BFF", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          resource_id: catalog.id,
          version_id: catalog.versions[0].id,
          external_id: "browser-catalog",
          version: "v1",
          created: true,
          item_count: 1,
          content_hash: "c".repeat(64),
          artifact_hash: "d".repeat(64),
        }),
        { status: 201, headers: { "content-type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <CatalogsConsole
        organizationId={organizationId}
        project={project}
        currentRole="ENGINEER"
        catalogs={[]}
      />,
    );

    const artifact = {
      catalog_id: "browser-catalog",
      version: "v1",
      products: [
        {
          product_id: "P-1",
          title: "Shoe",
          category: "shoes",
          price: "10",
          currency: "INR",
        },
      ],
    };
    const file = new File([JSON.stringify(artifact)], "catalog.json", {
      type: "application/json",
    });
    Object.defineProperty(file, "text", {
      value: vi.fn().mockResolvedValue(JSON.stringify(artifact)),
    });
    fireEvent.change(screen.getByLabelText("Catalog artifact"), {
      target: { files: [file] },
    });
    const form = screen
      .getByRole("button", { name: "Import immutable version" })
      .closest("form");
    expect(form).not.toBeNull();
    fireEvent.submit(form as HTMLFormElement);

    expect(await screen.findByRole("status")).toHaveTextContent(
      "browser-catalog v1 imported with 1 products",
    );
    expect(navigation.refresh).toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/organization/catalog-imports",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({ project_id: project.id, artifact }),
      }),
    );
  });

  it("keeps Reviewer access read-only", () => {
    render(
      <CatalogsConsole
        organizationId={organizationId}
        project={project}
        currentRole="REVIEWER"
        catalogs={[catalog]}
      />,
    );

    expect(screen.getByText("Read-only catalog access")).toBeInTheDocument();
    expect(screen.queryByLabelText("Catalog artifact")).not.toBeInTheDocument();
    expect(screen.getByText("ESCI Catalog")).toBeInTheDocument();
  });

  it("rejects invalid JSON before making a request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(
      <CatalogsConsole
        organizationId={organizationId}
        project={project}
        currentRole="ADMIN"
        catalogs={[]}
      />,
    );

    const file = new File(["not-json"], "broken.json", {
      type: "application/json",
    });
    Object.defineProperty(file, "text", {
      value: vi.fn().mockResolvedValue("not-json"),
    });
    fireEvent.change(screen.getByLabelText("Catalog artifact"), {
      target: { files: [file] },
    });
    const form = screen
      .getByRole("button", { name: "Import immutable version" })
      .closest("form");
    expect(form).not.toBeNull();
    fireEvent.submit(form as HTMLFormElement);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Catalog file must contain valid UTF-8 JSON",
    );
    await waitFor(() => expect(fetchMock).not.toHaveBeenCalled());
  });
});
