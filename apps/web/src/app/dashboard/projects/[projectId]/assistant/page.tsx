import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { AssistantPlayground } from "@/components/assistant-playground";
import {
  getOrganizationProjects,
  getProjectAISystems,
  getProjectCatalogs,
} from "@/lib/organization-api";
import { getCurrentUser } from "@/lib/server-auth";

export const metadata: Metadata = { title: "Assistant Playground" };
export const dynamic = "force-dynamic";

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export default async function AssistantPage({
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
  const [catalogs, systems] = await Promise.all([
    getProjectCatalogs(membership.organization_id, project.id),
    getProjectAISystems(membership.organization_id, project.id),
  ]);

  return (
    <div className="dashboard-stack assistant-page">
      <Link className="project-back-link" href={`/dashboard/projects/${project.id}`}>
        ← {project.name}
      </Link>
      <section className="page-heading assistant-page-heading">
        <div>
          <p className="eyebrow">ASSISTANT PLAYGROUND</p>
          <h1>Ask. Retrieve. Verify.</h1>
          <p>
            Inspect grounded product recommendations and every catalog citation
            before enabling model-based generation.
          </p>
        </div>
        <div className="status-pill"><span /> Evidence first</div>
      </section>
      <AssistantPlayground
        organizationId={membership.organization_id}
        project={project}
        catalogs={catalogs}
        systems={systems}
      />
    </div>
  );
}
