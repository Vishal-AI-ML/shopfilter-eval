"use client";

import { FormEvent, useMemo, useState } from "react";

import { errorMessage } from "@/lib/api-errors";
import type { MembershipRole } from "@/lib/auth-types";
import type {
  OrganizationInvitation,
  OrganizationMember,
} from "@/lib/organization-types";

const ROLES: MembershipRole[] = [
  "OWNER",
  "ADMIN",
  "ENGINEER",
  "REVIEWER",
  "VIEWER",
];

interface MembersConsoleProps {
  organizationId: string;
  currentUserId: string;
  currentRole: MembershipRole;
  initialMembers: OrganizationMember[];
  initialInvitations: OrganizationInvitation[];
}

async function responseError(
  response: Response,
  fallback: string,
): Promise<string> {
  const body: unknown = await response.json().catch(() => null);
  return errorMessage(body, fallback);
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function MembersConsole({
  organizationId,
  currentUserId,
  currentRole,
  initialMembers,
  initialInvitations,
}: MembersConsoleProps): React.ReactElement {
  const [members, setMembers] = useState(initialMembers);
  const [invitations, setInvitations] = useState(initialInvitations);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const ownerCount = useMemo(
    () => members.filter((member) => member.role === "OWNER").length,
    [members],
  );
  const isOwner = currentRole === "OWNER";
  const availableRoles = isOwner ? ROLES : ROLES.filter((role) => role !== "OWNER");
  const headers = {
    "content-type": "application/json",
    "x-organization-id": organizationId,
  };

  async function invite(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    setNotice(null);
    const form = event.currentTarget;
    const data = new FormData(form);
    const email = String(data.get("email") ?? "").trim();
    const role = String(data.get("role") ?? "VIEWER") as MembershipRole;
    setPendingAction("invite");
    try {
      const response = await fetch("/api/organization/invitations", {
        method: "POST",
        credentials: "same-origin",
        headers,
        body: JSON.stringify({ email, role }),
      });
      if (!response.ok) {
        setError(await responseError(response, "Unable to send invitation."));
        return;
      }
      const invitation = (await response.json()) as OrganizationInvitation;
      setInvitations((current) => [
        invitation,
        ...current.filter((item) => item.email !== invitation.email),
      ]);
      form.reset();
      setNotice(`Invitation sent to ${invitation.email}.`);
    } catch {
      setError("Invitation service is unavailable. Please try again.");
    } finally {
      setPendingAction(null);
    }
  }

  async function resend(invitation: OrganizationInvitation): Promise<void> {
    setError(null);
    setNotice(null);
    setPendingAction(`resend:${invitation.id}`);
    try {
      const response = await fetch("/api/organization/invitations", {
        method: "POST",
        credentials: "same-origin",
        headers,
        body: JSON.stringify({ email: invitation.email, role: invitation.role }),
      });
      if (!response.ok) {
        setError(await responseError(response, "Unable to resend invitation."));
        return;
      }
      const replacement = (await response.json()) as OrganizationInvitation;
      setInvitations((current) => [
        replacement,
        ...current.filter((item) => item.id !== invitation.id),
      ]);
      setNotice(`A new invitation link was sent to ${replacement.email}.`);
    } catch {
      setError("Invitation service is unavailable. Please try again.");
    } finally {
      setPendingAction(null);
    }
  }

  async function revoke(invitation: OrganizationInvitation): Promise<void> {
    setError(null);
    setNotice(null);
    setPendingAction(`revoke:${invitation.id}`);
    try {
      const response = await fetch(
        `/api/organization/invitations/${invitation.id}`,
        {
          method: "DELETE",
          credentials: "same-origin",
          headers: { "x-organization-id": organizationId },
        },
      );
      if (!response.ok) {
        setError(await responseError(response, "Unable to revoke invitation."));
        return;
      }
      setInvitations((current) =>
        current.filter((item) => item.id !== invitation.id),
      );
      setNotice(`Invitation for ${invitation.email} revoked.`);
    } catch {
      setError("Invitation service is unavailable. Please try again.");
    } finally {
      setPendingAction(null);
    }
  }

  async function changeRole(
    member: OrganizationMember,
    role: MembershipRole,
  ): Promise<void> {
    if (role === member.role) return;
    setError(null);
    setNotice(null);
    setPendingAction(`role:${member.id}`);
    try {
      const response = await fetch(`/api/organization/members/${member.id}`, {
        method: "PATCH",
        credentials: "same-origin",
        headers,
        body: JSON.stringify({ role }),
      });
      if (!response.ok) {
        setError(await responseError(response, "Unable to change member role."));
        return;
      }
      const updated = (await response.json()) as OrganizationMember;
      setMembers((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
      setNotice(`${updated.display_name} is now ${updated.role}.`);
      if (updated.user_id === currentUserId) window.location.reload();
    } catch {
      setError("Membership service is unavailable. Please try again.");
    } finally {
      setPendingAction(null);
    }
  }

  async function remove(member: OrganizationMember): Promise<void> {
    if (!window.confirm(`Remove ${member.display_name} from this organization?`)) {
      return;
    }
    setError(null);
    setNotice(null);
    setPendingAction(`remove:${member.id}`);
    try {
      const response = await fetch(`/api/organization/members/${member.id}`, {
        method: "DELETE",
        credentials: "same-origin",
        headers: { "x-organization-id": organizationId },
      });
      if (!response.ok) {
        setError(await responseError(response, "Unable to remove member."));
        return;
      }
      setMembers((current) => current.filter((item) => item.id !== member.id));
      setNotice(`${member.display_name} was removed.`);
      if (member.user_id === currentUserId) window.location.reload();
    } catch {
      setError("Membership service is unavailable. Please try again.");
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="members-layout">
      <section className="invite-panel" aria-labelledby="invite-heading">
        <div>
          <p className="eyebrow">TEAM ACCESS</p>
          <h2 id="invite-heading">Invite a teammate</h2>
          <p>
            Invitation links are expiring, single-use, and stored only as a hash.
          </p>
        </div>
        <form className="invite-form" onSubmit={invite}>
          <div className="field">
            <label htmlFor="invite-email">Work email</label>
            <input
              id="invite-email"
              name="email"
              type="email"
              maxLength={320}
              autoComplete="email"
              required
            />
          </div>
          <div className="field">
            <label htmlFor="invite-role">Role</label>
            <select id="invite-role" name="role" defaultValue="VIEWER">
              {availableRoles.map((role) => (
                <option value={role} key={role}>{role}</option>
              ))}
            </select>
          </div>
          <button
            className="primary-button invite-button"
            disabled={pendingAction === "invite"}
          >
            {pendingAction === "invite" ? "Sending…" : "Send invitation"}
          </button>
        </form>
      </section>

      {error ? <div className="form-error members-message" role="alert">{error}</div> : null}
      {notice ? <div className="form-success members-message" role="status">{notice}</div> : null}

      <section className="team-section" aria-labelledby="members-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">ACTIVE ACCESS</p>
            <h2 id="members-heading">Organization members</h2>
          </div>
          <span>{members.length} {members.length === 1 ? "member" : "members"}</span>
        </div>
        <div className="team-table" role="table" aria-label="Organization members">
          <div className="team-row team-header" role="row">
            <span>Member</span><span>Role</span><span>Joined</span><span>Action</span>
          </div>
          {members.map((member) => {
            const lastOwner = member.role === "OWNER" && ownerCount === 1;
            const adminBlocked = !isOwner && member.role === "OWNER";
            const locked = lastOwner || adminBlocked;
            return (
              <div className="team-row" role="row" key={member.id}>
                <div className="member-identity" role="cell">
                  <span className="member-avatar">{initials(member.display_name)}</span>
                  <div>
                    <strong>{member.display_name}</strong>
                    <span>{member.email}</span>
                    {member.user_id === currentUserId ? <small>You</small> : null}
                  </div>
                </div>
                <div role="cell">
                  <select
                    className="role-select"
                    aria-label={`Role for ${member.display_name}`}
                    value={member.role}
                    disabled={locked || pendingAction === `role:${member.id}`}
                    onChange={(event) =>
                      void changeRole(member, event.target.value as MembershipRole)
                    }
                  >
                    {ROLES.map((role) => (
                      <option
                        value={role}
                        key={role}
                        disabled={!isOwner && role === "OWNER"}
                      >
                        {role}
                      </option>
                    ))}
                  </select>
                  {lastOwner ? <small className="owner-lock">Last Owner protected</small> : null}
                  {adminBlocked ? <small className="owner-lock">Owner-managed only</small> : null}
                </div>
                <span className="date-cell" role="cell">
                  {new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(member.created_at))}
                </span>
                <div role="cell">
                  <button
                    className="danger-button"
                    disabled={locked || pendingAction === `remove:${member.id}`}
                    onClick={() => void remove(member)}
                  >
                    {pendingAction === `remove:${member.id}` ? "Removing…" : "Remove"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </section>

      <section className="team-section" aria-labelledby="pending-heading">
        <div className="section-heading">
          <div>
            <p className="eyebrow">AWAITING ACCEPTANCE</p>
            <h2 id="pending-heading">Pending invitations</h2>
          </div>
          <span>{invitations.length} pending</span>
        </div>
        {invitations.length === 0 ? (
          <div className="empty-team-state">
            <strong>No pending invitations</strong>
            <span>New invitations will appear here until accepted, revoked, or expired.</span>
          </div>
        ) : (
          <div className="invitation-list">
            {invitations.map((invitation) => {
              const ownerBlocked = !isOwner && invitation.role === "OWNER";
              return (
                <article className="invitation-row" key={invitation.id}>
                  <div>
                    <strong>{invitation.email}</strong>
                    <span>
                      {invitation.role} · expires {new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(invitation.expires_at))}
                    </span>
                  </div>
                  <div className="invitation-actions">
                    <button
                      className="secondary-button compact-button"
                      disabled={ownerBlocked || pendingAction === `resend:${invitation.id}`}
                      onClick={() => void resend(invitation)}
                    >
                      {pendingAction === `resend:${invitation.id}` ? "Sending…" : "Resend"}
                    </button>
                    <button
                      className="danger-button"
                      disabled={ownerBlocked || pendingAction === `revoke:${invitation.id}`}
                      onClick={() => void revoke(invitation)}
                    >
                      {pendingAction === `revoke:${invitation.id}` ? "Revoking…" : "Revoke"}
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </div>
  );
}
