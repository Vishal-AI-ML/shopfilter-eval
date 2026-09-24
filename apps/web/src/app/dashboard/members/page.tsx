import type { Metadata } from "next";
import { redirect } from "next/navigation";

import { MembersConsole } from "@/components/members-console";
import {
  getOrganizationInvitations,
  getOrganizationMembers,
} from "@/lib/organization-api";
import { can } from "@/lib/permissions";
import { getCurrentUser } from "@/lib/server-auth";

export const metadata: Metadata = { title: "Members" };
export const dynamic = "force-dynamic";

export default async function MembersPage(): Promise<React.ReactElement> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  const membership = user.memberships[0];
  if (
    !membership ||
    !user.email_verified ||
    !can(membership.role, "manage_members")
  ) {
    redirect("/dashboard");
  }

  const [members, invitations] = await Promise.all([
    getOrganizationMembers(membership.organization_id),
    getOrganizationInvitations(membership.organization_id),
  ]);

  return (
    <div className="dashboard-stack">
      <section className="page-heading members-heading">
        <div>
          <p className="eyebrow">ORGANIZATION GOVERNANCE</p>
          <h1>Members & invitations</h1>
          <p>
            Manage active access, issue secure invitations, and preserve Owner
            governance.
          </p>
        </div>
        <div className="status-pill"><span /> Verified manager</div>
      </section>
      <MembersConsole
        organizationId={membership.organization_id}
        currentUserId={user.id}
        currentRole={membership.role}
        initialMembers={members}
        initialInvitations={invitations}
      />
    </div>
  );
}
