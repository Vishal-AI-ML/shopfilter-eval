import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MembersConsole } from "@/components/members-console";
import type {
  OrganizationInvitation,
  OrganizationMember,
} from "@/lib/organization-types";

const organizationId = "e5150000-0000-4000-8000-000000000001";
const owner: OrganizationMember = {
  id: "11111111-1111-4111-8111-111111111111",
  organization_id: organizationId,
  user_id: "22222222-2222-4222-8222-222222222222",
  email: "owner@example.com",
  display_name: "Primary Owner",
  role: "OWNER",
  created_at: "2026-09-24T12:00:00Z",
};
const pendingInvitation: OrganizationInvitation = {
  id: "33333333-3333-4333-8333-333333333333",
  organization_id: organizationId,
  email: "reviewer@example.com",
  role: "REVIEWER",
  created_at: "2026-09-24T12:00:00Z",
  expires_at: "2026-10-01T12:00:00Z",
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("MembersConsole", () => {
  it("surfaces last-Owner protection and pending invitations", () => {
    render(
      <MembersConsole
        organizationId={organizationId}
        currentUserId={owner.user_id}
        currentRole="OWNER"
        initialMembers={[owner]}
        initialInvitations={[pendingInvitation]}
      />,
    );

    expect(screen.getByText("Last Owner protected")).toBeInTheDocument();
    expect(screen.getByLabelText("Role for Primary Owner")).toBeDisabled();
    expect(screen.getByText("reviewer@example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resend" })).toBeEnabled();
  });

  it("issues an invitation through the same-origin organization BFF", async () => {
    const created: OrganizationInvitation = {
      ...pendingInvitation,
      id: "44444444-4444-4444-8444-444444444444",
      email: "engineer@example.com",
      role: "ENGINEER",
    };
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify(created), {
        status: 201,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(
      <MembersConsole
        organizationId={organizationId}
        currentUserId={owner.user_id}
        currentRole="OWNER"
        initialMembers={[owner]}
        initialInvitations={[]}
      />,
    );

    fireEvent.change(screen.getByLabelText("Work email"), {
      target: { value: "engineer@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Role"), {
      target: { value: "ENGINEER" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send invitation" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Invitation sent to engineer@example.com",
    );
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/organization/invitations",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({
          email: "engineer@example.com",
          role: "ENGINEER",
        }),
      }),
    );
  });

  it("prevents an Admin from managing Owner access", () => {
    render(
      <MembersConsole
        organizationId={organizationId}
        currentUserId="55555555-5555-4555-8555-555555555555"
        currentRole="ADMIN"
        initialMembers={[owner]}
        initialInvitations={[{ ...pendingInvitation, role: "OWNER" }]}
      />,
    );

    expect(
      within(screen.getByLabelText("Role")).queryByRole("option", { name: "OWNER" }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Owner-managed only")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Resend" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Revoke" })).toBeDisabled();
  });

  it("shows the backend last-Owner conflict without mutating local state", async () => {
    const secondOwner: OrganizationMember = {
      ...owner,
      id: "66666666-6666-4666-8666-666666666666",
      user_id: "77777777-7777-4777-8777-777777777777",
      email: "second@example.com",
      display_name: "Second Owner",
    };
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ detail: "Organization must retain at least one Owner" }),
          { status: 409, headers: { "content-type": "application/json" } },
        ),
      ),
    );
    render(
      <MembersConsole
        organizationId={organizationId}
        currentUserId={owner.user_id}
        currentRole="OWNER"
        initialMembers={[owner, secondOwner]}
        initialInvitations={[]}
      />,
    );

    fireEvent.change(screen.getByLabelText("Role for Primary Owner"), {
      target: { value: "ADMIN" },
    });

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Organization must retain at least one Owner",
    );
    await waitFor(() =>
      expect(screen.getByLabelText("Role for Primary Owner")).toHaveValue("OWNER"),
    );
  });
});
