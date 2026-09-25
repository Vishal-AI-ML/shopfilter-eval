import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { CatalogsConsole } from "@/components/catalogs-console";
import {
  getOrganizationProjects,
  getProjectCatalogs,
} from "@/lib/organization-api";
import { getCurrentUser } from "@/lib/server-auth";

export const metadata: Metadata = { title: "Catalogs" };
export const dynamic = "force-dynamic";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default async function CatalogsPage({
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
  const catalogs = await getProjectCatalogs(membership.organization_id, project.id);

  return (
    <div className="dashboard-stack">
      <Link className="project-back-link" href={`/dashboard/projects/${project.id}`}>
        ← {project.name}
      </Link>
      <section className="page-heading catalog-page-heading">
        <div>
          <p className="eyebrow">PROJECT CATALOGS</p>
          <h1>Catalog inventory</h1>
          <p>
            Validate product content and inspect immutable versions for
            <strong> {project.name}</strong>.
          </p>
        </div>
        <div className="status-pill"><span /> Project scoped</div>
      </section>
      <CatalogsConsole
        organizationId={membership.organization_id}
        project={project}
        currentRole={membership.role}
        catalogs={catalogs}
      />
    </div>
  );
}
