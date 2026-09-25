import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { getOrganizationProjects } from "@/lib/organization-api";
import { getCurrentUser } from "@/lib/server-auth";

export const metadata: Metadata = { title: "Project workspace" };
export const dynamic = "force-dynamic";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default async function ProjectWorkspacePage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}): Promise<React.ReactElement> {
  const { projectId } = await params;
  if (!UUID_PATTERN.test(projectId)) notFound();

  const user = await getCurrentUser();
  if (!user) redirect("/login");
  const membership = user.memberships[0];
  if (!membership) redirect("/dashboard");

  const projects = await getOrganizationProjects(membership.organization_id);
  const project = projects.find((item) => item.id === projectId);
  if (!project) notFound();

  return (
    <div className="dashboard-stack">
      <Link className="project-back-link" href="/dashboard/projects">← All projects</Link>
      <section className="project-context-hero">
        <div>
          <p className="eyebrow">SELECTED PROJECT</p>
          <h1>{project.name}</h1>
          <p>
            Project context is encoded in this tenant-protected URL. Downstream
            resources will remain scoped to this project.
          </p>
        </div>
        <div className="project-context-id">
          <span>Slug</span>
          <strong>{project.slug}</strong>
          <small>{project.id}</small>
        </div>
      </section>

      <section className="project-module-grid" aria-label="Project modules">
        <Link
          className="project-module-card next-module available-module"
          href={`/dashboard/projects/${project.id}/catalogs`}
        >
          <span>01</span>
          <div><p className="eyebrow">AVAILABLE NOW</p><h2>Catalogs</h2></div>
          <p>Import, validate, version, and publish product catalogs.</p>
          <small>Open catalogs →</small>
        </Link>
        <article className="project-module-card">
          <span>02</span>
          <div><p className="eyebrow">CONFIGURATION</p><h2>Search systems</h2></div>
          <p>Connect provider versions and inspect supported trace evidence.</p>
          <small>Planned</small>
        </article>
        <article className="project-module-card">
          <span>03</span>
          <div><p className="eyebrow">GROUND TRUTH</p><h2>Datasets</h2></div>
          <p>Review immutable golden cases against exact catalog versions.</p>
          <small>Planned</small>
        </article>
        <article className="project-module-card">
          <span>04</span>
          <div><p className="eyebrow">EXECUTION</p><h2>Evaluation runs</h2></div>
          <p>Start durable jobs and inspect metrics, failures, and artifacts.</p>
          <small>Planned</small>
        </article>
      </section>

      <section className="project-context-footer">
        <div><strong>Organization</strong><span>{project.organization_id}</span></div>
        <div><strong>Created</strong><span>{new Intl.DateTimeFormat("en", { dateStyle: "long" }).format(new Date(project.created_at))}</span></div>
        <div><strong>Your role</strong><span>{membership.role}</span></div>
      </section>
    </div>
  );
}
