import { redirect } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { getCurrentUser } from "@/lib/server-auth";

export default async function DashboardLayout({
  children,
}: Readonly<{ children: React.ReactNode }>): Promise<React.ReactElement> {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  const membership = user.memberships[0];
  if (!membership) {
    return (
      <main className="centered-state">
        <div className="state-card">
          <p className="eyebrow">NO WORKSPACE ACCESS</p>
          <h1>Organization membership required</h1>
          <p>Your account is active but is not assigned to an organization.</p>
        </div>
      </main>
    );
  }

  return <AppShell user={user} membership={membership}>{children}</AppShell>;
}
