"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";

import { errorMessage } from "@/lib/api-errors";
import type { MembershipRole } from "@/lib/auth-types";
import { can } from "@/lib/permissions";
import type { ProjectSummary } from "@/lib/project-types";

function slugify(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 100);
}

export function ProjectsConsole({
  organizationId,
  currentRole,
  initialProjects,
}: {
  organizationId: string;
  currentRole: MembershipRole;
  initialProjects: ProjectSummary[];
}): React.ReactElement {
  const [projects, setProjects] = useState(initialProjects);
  const [query, setQuery] = useState("");
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const canCreate = can(currentRole, "manage_projects");
  const visibleProjects = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return projects;
    return projects.filter(
      (project) =>
        project.name.toLowerCase().includes(normalized) ||
        project.slug.toLowerCase().includes(normalized),
    );
  }, [projects, query]);

  async function createProject(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setPending(true);
    try {
      const response = await fetch("/api/organization/projects", {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "content-type": "application/json",
          "x-organization-id": organizationId,
        },
        body: JSON.stringify({ name, slug }),
      });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        setError(errorMessage(body, "Unable to create project."));
        return;
      }
      const project = body as ProjectSummary;
      setProjects((current) =>
        [...current, project].sort((left, right) =>
          left.name.localeCompare(right.name),
        ),
      );
      setName("");
      setSlug("");
      setSlugEdited(false);
      setNotice(`${project.name} is ready.`);
    } catch {
      setError("Project service is unavailable. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="projects-layout">
      {canCreate ? (
        <section className="project-create-panel" aria-labelledby="create-project-heading">
          <div>
            <p className="eyebrow">NEW WORKSPACE</p>
            <h2 id="create-project-heading">Create a project</h2>
            <p>
              Projects isolate catalogs, datasets, search systems, and evaluation
              evidence inside this organization.
            </p>
          </div>
          <form className="project-create-form" onSubmit={createProject}>
            <div className="field">
              <label htmlFor="project-name">Project name</label>
              <input
                id="project-name"
                name="name"
                value={name}
                minLength={1}
                maxLength={200}
                required
                onChange={(event) => {
                  const value = event.target.value;
                  setName(value);
                  if (!slugEdited) setSlug(slugify(value));
                }}
              />
            </div>
            <div className="field">
              <label htmlFor="project-slug">Project slug</label>
              <input
                id="project-slug"
                name="slug"
                value={slug}
                minLength={1}
                maxLength={100}
                pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
                required
                onChange={(event) => {
                  setSlug(event.target.value.toLowerCase());
                  setSlugEdited(true);
                }}
              />
            </div>
            <button className="primary-button" disabled={pending || !slug}>
              {pending ? "Creating…" : "Create project"}
            </button>
          </form>
        </section>
      ) : (
        <section className="project-readonly-note">
          <strong>Read-only project access</strong>
          <span>Your {currentRole} role can inspect projects but cannot create them.</span>
        </section>
      )}

      {error ? <div className="form-error" role="alert">{error}</div> : null}
      {notice ? <div className="form-success" role="status">{notice}</div> : null}

      <section className="projects-section" aria-labelledby="projects-list-heading">
        <div className="section-heading projects-list-heading">
          <div>
            <p className="eyebrow">ORGANIZATION SCOPE</p>
            <h2 id="projects-list-heading">Projects</h2>
          </div>
          <div className="project-list-tools">
            <label className="project-search">
              <span className="sr-only">Search projects</span>
              <input
                type="search"
                placeholder="Search projects"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <span className="project-count">{projects.length} total</span>
          </div>
        </div>

        {projects.length === 0 ? (
          <div className="empty-project-state">
            <span className="empty-project-mark" aria-hidden="true">P</span>
            <strong>No projects yet</strong>
            <p>
              {canCreate
                ? "Create the first project to scope catalogs and evaluations."
                : "A project creator has not added a workspace yet."}
            </p>
          </div>
        ) : visibleProjects.length === 0 ? (
          <div className="empty-project-state compact-empty">
            <strong>No matching projects</strong>
            <p>Try a different name or slug.</p>
          </div>
        ) : (
          <div className="project-grid">
            {visibleProjects.map((project, index) => (
              <article className="project-card" key={project.id}>
                <div className="project-card-top">
                  <span className="project-index">{String(index + 1).padStart(2, "0")}</span>
                  <span className="project-status"><i /> Active</span>
                </div>
                <div>
                  <h3>{project.name}</h3>
                  <p>{project.slug}</p>
                </div>
                <dl className="project-meta">
                  <div>
                    <dt>Created</dt>
                    <dd>{new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(project.created_at))}</dd>
                  </div>
                  <div>
                    <dt>Project ID</dt>
                    <dd>{project.id.slice(0, 8)}</dd>
                  </div>
                </dl>
                <Link className="project-open-link" href={`/dashboard/projects/${project.id}`}>
                  Open workspace <span aria-hidden="true">→</span>
                </Link>
              </article>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
