import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const navigation = vi.hoisted(() => ({ replace: vi.fn(), refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => navigation }));

import { AcceptInvitationForm } from "@/components/accept-invitation-form";

afterEach(() => {
  vi.unstubAllGlobals();
  navigation.replace.mockReset();
  navigation.refresh.mockReset();
});

describe("AcceptInvitationForm", () => {
  it("accepts a single-use invitation through the same-origin BFF", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<AcceptInvitationForm token="single-use-invitation-token-value" />);
    fireEvent.change(screen.getByLabelText(/Your name/), { target: { value: "New Member" } });
    fireEvent.change(screen.getByLabelText("Account password"), { target: { value: "invitation-test-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Accept invitation" }));

    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/dashboard"));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/accept-invitation",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({
          token: "single-use-invitation-token-value",
          display_name: "New Member",
          password: "invitation-test-password",
        }),
      }),
    );
  });

  it("shows a safe acceptance error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      JSON.stringify({ detail: "Unable to accept invitation" }),
      { status: 400, headers: { "content-type": "application/json" } },
    )));
    render(<AcceptInvitationForm token="expired-invitation-token-value" />);
    fireEvent.change(screen.getByLabelText("Account password"), { target: { value: "invitation-test-password" } });
    fireEvent.click(screen.getByRole("button", { name: "Accept invitation" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Unable to accept invitation");
  });
});
