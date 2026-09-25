import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { ProjectsConsole } from "@/components/projects-console";
import { getOrganizationProjects } from "@/lib/organization-api";
import { getCurrentUser } from "@/lib/server-auth";

export const metadata: Metadata = { title: "Projects" };
export const dynamic = "force-dynamic";

export default async function ProjectsPage(): Promise<React.ReactElement> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  const membership = user.memberships[0];
  if (!membership) redirect("/dashboard");

  const projects = await getOrganizationProjects(membership.organization_id);

  return (
    <div className="dashboard-stack">
      <section className="page-heading">
        <div>
          <p className="eyebrow">TENANT WORKSPACES</p>
          <h1>Projects</h1>
          <p>
            Select the scope for catalogs, datasets, search systems, and
            evaluation runs.
          </p>
        </div>
        <div className="status-pill"><span /> Tenant isolated</div>
      </section>
      <ProjectsConsole
        organizationId={membership.organization_id}
        currentRole={membership.role}
        initialProjects={projects}
      />
    </div>
  );
}
