import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const navigation = vi.hoisted(() => ({ replace: vi.fn(), refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => navigation }));

import { EmailVerificationPanel } from "@/components/email-verification-panel";

afterEach(() => {
  vi.unstubAllGlobals();
  navigation.replace.mockReset();
  navigation.refresh.mockReset();
});

describe("EmailVerificationPanel", () => {
  it("exchanges the link token through the same-origin BFF and removes it from the URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ message: "Email verified successfully." }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    render(<EmailVerificationPanel token="single-use-token-value-1234567890" />);

    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/verify-email?status=success"));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/verify-email",
      expect.objectContaining({
        method: "POST",
        credentials: "same-origin",
        body: JSON.stringify({ token: "single-use-token-value-1234567890" }),
      }),
    );
    expect(await screen.findByText("Email verified. Your account is ready.")).toBeInTheDocument();
  });

  it("does not expose a rejected token and offers a resend action", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Invalid or expired email verification link" }), {
        status: 400,
        headers: { "content-type": "application/json" },
      }),
    ));
    render(<EmailVerificationPanel token="expired-token-value-123456789012345" />);
    expect(await screen.findByText("Invalid or expired email verification link")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send another link" })).toBeInTheDocument();
  });
});
