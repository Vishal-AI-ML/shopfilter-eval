import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const navigation = vi.hoisted(() => ({
  replace: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => navigation,
}));

import { LoginForm } from "@/components/login-form";

afterEach(() => {
  vi.unstubAllGlobals();
  navigation.replace.mockReset();
  navigation.refresh.mockReset();
});

describe("LoginForm", () => {
  it("submits credentials to the same-origin auth route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ user: {}, expires_at: "future" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText("Work email"), {
      target: { value: "owner@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "local-password" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in securely" }));

    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/dashboard"));
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/auth/login",
      expect.objectContaining({ method: "POST", credentials: "same-origin" }),
    );
  });

  it("shows safe API errors without navigating", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Invalid email or password" }), {
          status: 401,
          headers: { "content-type": "application/json" },
        }),
      ),
    );

    render(<LoginForm />);
    fireEvent.change(screen.getByLabelText("Work email"), {
      target: { value: "owner@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in securely" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Invalid email or password");
    expect(navigation.replace).not.toHaveBeenCalled();
  });
});
