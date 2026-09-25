import { describe, expect, it } from "vitest";

import { can } from "@/lib/permissions";

describe("role capabilities", () => {
  it("keeps viewers read-only", () => {
    expect(can("VIEWER", "view")).toBe(true);
    expect(can("VIEWER", "execute_evaluation")).toBe(false);
    expect(can("VIEWER", "review_dataset")).toBe(false);
    expect(can("VIEWER", "manage_projects")).toBe(false);
    expect(can("VIEWER", "manage_members")).toBe(false);
  });

  it("allows reviewers to review without granting execution", () => {
    expect(can("REVIEWER", "review_dataset")).toBe(true);
    expect(can("REVIEWER", "execute_evaluation")).toBe(false);
    expect(can("REVIEWER", "manage_projects")).toBe(false);
  });

  it("allows engineers to execute and create projects without managing members", () => {
    expect(can("ENGINEER", "execute_evaluation")).toBe(true);
    expect(can("ENGINEER", "manage_projects")).toBe(true);
    expect(can("ENGINEER", "manage_members")).toBe(false);
  });

  it("allows owners and admins to manage projects and members", () => {
    expect(can("OWNER", "manage_projects")).toBe(true);
    expect(can("ADMIN", "manage_projects")).toBe(true);
    expect(can("OWNER", "manage_members")).toBe(true);
    expect(can("ADMIN", "manage_members")).toBe(true);
  });
});
