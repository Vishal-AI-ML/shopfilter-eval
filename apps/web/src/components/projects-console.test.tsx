import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectsConsole } from "@/components/projects-console";
import type { ProjectSummary } from "@/lib/project-types";

const organizationId = "e5150000-0000-4000-8000-000000000001";
const project: ProjectSummary = {
  id: "e5150000-0000-4000-8000-000000000002",
  organization_id: organizationId,
  name: "Search Quality",
  slug: "search-quality",
  created_at: "2026-09-24T12:00:00Z",
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ProjectsConsole", () => {
  it("renders tenant projects with URL-based workspace links", () => {
    render(
      <ProjectsConsole
        organizationId={organizationId}
        currentRole="OWNER"
        initialProjects={[project]}
      />,
    );

    expect(screen.getByText("Search Quality")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Open workspace/ })).toHaveAttribute(
      "href",
      `/dashboard/projects/${project.id}`,
    );
  });

  it("creates a normalized project through the same-origin BFF", async () => {
    const created: ProjectSummary = {
      ...project,
      id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      name: "Indian Fashion Search",
      slug: "indian-fashion-search",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(created), {
        status: 201,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <ProjectsConsole
        organizationId={organizationId}
        currentRole="ENGINEER"
        initialProjects={[]}
      />,
    );

    fireEvent.change(screen.getByLabelText("Project name"), {
      target: { value: "Indian Fashion Search" },
    });
    expect(screen.getByLabelText("Project slug")).toHaveValue(
      "indian-fashion-search",
    );
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Indian Fashion Search is ready",
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/organization/projects",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({
          name: "Indian Fashion Search",
          slug: "indian-fashion-search",
        }),
      }),
    );
  });

  it("keeps Viewer access read-only while preserving project visibility", () => {
    render(
      <ProjectsConsole
        organizationId={organizationId}
        currentRole="VIEWER"
        initialProjects={[project]}
      />,
    );

    expect(screen.getByText("Read-only project access")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Create project" })).not.toBeInTheDocument();
    expect(screen.getByText("Search Quality")).toBeInTheDocument();
  });

  it("shows safe duplicate-slug errors without adding a project", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ detail: "Project slug already exists in this organization" }),
          { status: 409, headers: { "content-type": "application/json" } },
        ),
      ),
    );
    render(
      <ProjectsConsole
        organizationId={organizationId}
        currentRole="ADMIN"
        initialProjects={[project]}
      />,
    );

    fireEvent.change(screen.getByLabelText("Project name"), {
      target: { value: "Search Quality" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create project" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Project slug already exists in this organization",
    );
    await waitFor(() =>
      expect(screen.getAllByText("Search Quality")).toHaveLength(1),
    );
  });
});
