import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AssistantPlayground } from "@/components/assistant-playground";
import type { AISystemWithVersions } from "@/lib/assistant-types";
import type { CatalogWithVersions } from "@/lib/catalog-types";
import type { ProjectSummary } from "@/lib/project-types";

const organizationId = "e5150000-0000-4000-8000-000000000001";
const project: ProjectSummary = {
  id: "e5150000-0000-4000-8000-000000000002",
  organization_id: organizationId,
  name: "Shopping Quality",
  slug: "shopping-quality",
  created_at: "2026-09-25T10:00:00Z",
};
const catalogs: CatalogWithVersions[] = [{
  id: "11111111-1111-4111-8111-111111111111",
  organization_id: organizationId,
  project_id: project.id,
  external_id: "controlled-catalog",
  name: "Controlled Catalog",
  created_at: "2026-09-25T10:00:00Z",
  versions: [{
    id: "22222222-2222-4222-8222-222222222222",
    organization_id: organizationId,
    catalog_id: "11111111-1111-4111-8111-111111111111",
    version: "v1",
    status: "PUBLISHED",
    content_hash: "a".repeat(64),
    artifact_hash: "b".repeat(64),
    item_count: 100,
    provenance: {},
    created_at: "2026-09-25T10:00:00Z",
  }],
}];
const systems: AISystemWithVersions[] = [{
  id: "33333333-3333-4333-8333-333333333333",
  organization_id: organizationId,
  project_id: project.id,
  name: "Reference Assistant",
  system_type: "RAG_ASSISTANT",
  provider: "deterministic-reference",
  description: null,
  status: "ACTIVE",
  created_at: "2026-09-25T10:00:00Z",
  versions: [{
    id: "44444444-4444-4444-8444-444444444444",
    organization_id: organizationId,
    ai_system_id: "33333333-3333-4333-8333-333333333333",
    version: "reference-v1",
    configuration: {},
    capabilities: { lexical_retrieval: true, citations: true },
    status: "PUBLISHED",
    content_hash: "c".repeat(64),
    created_at: "2026-09-25T10:00:00Z",
  }],
}];

const response = {
  answer: "I found 1 verified catalog match. Top evidence-backed options: Black Running Shoe (INR 2499) [SHOE-1].",
  mode: "DETERMINISTIC_REFERENCE",
  generation_provider: "DISABLED",
  system: {
    id: systems[0].id,
    version_id: systems[0].versions[0].id,
    name: systems[0].name,
    version: "reference-v1",
    system_type: "RAG_ASSISTANT",
    provider: "deterministic-reference",
    capabilities: { lexical_retrieval: true, citations: true },
    content_hash: "c".repeat(64),
  },
  catalog: {
    id: catalogs[0].id,
    version_id: catalogs[0].versions[0].id,
    name: catalogs[0].name,
    external_id: "controlled-catalog",
    version: "v1",
    content_hash: "a".repeat(64),
  },
  interpreted_query: { query_text: "running shoes" },
  applied_filters: { color: "black", max_price: "3000", availability: "in_stock" },
  retrieved_candidate_ids: ["SHOE-1", "SHOE-2"],
  filtered_candidate_ids: ["SHOE-1"],
  products: [{
    product_id: "SHOE-1",
    title: "Black Running Shoe",
    description: "Lightweight daily trainer",
    category: "shoes",
    brand: "Stride",
    color: "black",
    price: "2499",
    currency: "INR",
    availability: "in_stock",
    rank: 1,
    score: 1.75,
    score_breakdown: { title: 1.25, description: 0.5 },
    citation: {
      claim: "Black Running Shoe is listed at INR 2499.",
      source_id: "SHOE-1",
      source_version: "v1",
    },
  }],
  citations: [{
    claim: "Black Running Shoe is listed at INR 2499.",
    source_id: "SHOE-1",
    source_version: "v1",
  }],
  missing_information: [],
  latency_ms: 4.25,
} as const;

afterEach(() => vi.unstubAllGlobals());

describe("AssistantPlayground", () => {
  it("labels deterministic mode and published inputs honestly", () => {
    render(
      <AssistantPlayground
        organizationId={organizationId}
        project={project}
        catalogs={catalogs}
        systems={systems}
      />,
    );
    expect(screen.getByText("Deterministic reference mode")).toBeInTheDocument();
    expect(screen.getByText("Generator disabled · no fake LLM output")).toBeInTheDocument();
    expect(screen.getByLabelText("Catalog version")).toHaveValue(catalogs[0].versions[0].id);
    expect(screen.getByLabelText("AI system version")).toHaveValue(systems[0].versions[0].id);
  });

  it("renders grounded products, filters, and citations returned by the BFF", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(response), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <AssistantPlayground
        organizationId={organizationId}
        project={project}
        catalogs={catalogs}
        systems={systems}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Run grounded retrieval" }));

    expect(await screen.findByText("Black Running Shoe")).toBeInTheDocument();
    expect(screen.getByText("INR 2499")).toBeInTheDocument();
    expect(screen.getByText("Black Running Shoe is listed at INR 2499.")).toBeInTheDocument();
    expect(screen.getByText("DETERMINISTIC REFERENCE")).toBeInTheDocument();
    expect(screen.getByText("DISABLED")).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/organization/assistant-playground",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({
          project_id: project.id,
          catalog_version_id: catalogs[0].versions[0].id,
          ai_system_version_id: systems[0].versions[0].id,
          query: "wireless charger",
          top_k: 5,
        }),
      }),
    );
  });

  it("shows unavailable instead of inventing a zero-price claim", async () => {
    const unavailable = {
      ...response,
      answer: "I found 1 verified catalog match: Black Running Shoe [SHOE-1].",
      products: [{
        ...response.products[0],
        price: null,
        citation: {
          ...response.products[0].citation,
          claim: "Black Running Shoe appears in the selected catalog version.",
        },
      }],
      citations: [{
        ...response.citations[0],
        claim: "Black Running Shoe appears in the selected catalog version.",
      }],
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(unavailable), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    ));
    render(
      <AssistantPlayground
        organizationId={organizationId}
        project={project}
        catalogs={catalogs}
        systems={systems}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Run grounded retrieval" }));
    expect(await screen.findByText("Not available")).toBeInTheDocument();
    expect(screen.getByText("Black Running Shoe appears in the selected catalog version.")).toBeInTheDocument();
    expect(screen.queryByText("USD 0.00")).not.toBeInTheDocument();
  });

  it("shows setup guidance instead of pretending the assistant can run", () => {
    render(
      <AssistantPlayground
        organizationId={organizationId}
        project={project}
        catalogs={[]}
        systems={[]}
      />,
    );
    expect(screen.getByText("Published inputs are required")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Run grounded retrieval" })).not.toBeInTheDocument();
  });
});
