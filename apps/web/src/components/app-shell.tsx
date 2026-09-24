import type { AuthenticatedUser, Membership } from "@/lib/auth-types";
import { can } from "@/lib/permissions";
import { AppNavigation } from "@/components/app-navigation";
import { LogoutButton } from "@/components/logout-button";

interface AppShellProps {
  user: AuthenticatedUser;
  membership: Membership;
  children: React.ReactNode;
}

export function AppShell({
  user,
  membership,
  children,
}: AppShellProps): React.ReactElement {
  const canManageMembers =
    user.email_verified && can(membership.role, "manage_members");

  return (
    <div className="app-frame">
      <aside className="sidebar">
        <div className="brand compact-brand">
          <div className="brand-mark" aria-hidden="true">SF</div>
          <div>
            <strong>ShopFilter</strong>
            <span>Evaluation Console</span>
          </div>
        </div>
        <AppNavigation canManageMembers={canManageMembers} />
        <div className="sidebar-foot">
          <span className="environment-dot" /> Local development
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="organization-context">
            <span>Organization</span>
            <strong>{membership.organization_id}</strong>
          </div>
          <div className="user-context">
            <div className="user-copy">
              <strong>{user.display_name}</strong>
              <span>{membership.role}</span>
            </div>
            <LogoutButton />
          </div>
        </header>
        <main className="main-content">{children}</main>
      </div>
    </div>
  );
}
