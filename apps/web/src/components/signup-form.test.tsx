import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const navigation = vi.hoisted(() => ({ replace: vi.fn(), refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => navigation }));

import { SignupForm } from "@/components/signup-form";

afterEach(() => {
  vi.unstubAllGlobals();
  navigation.replace.mockReset();
  navigation.refresh.mockReset();
});

function fillForm(): void {
  fireEvent.change(screen.getByLabelText("Your name"), { target: { value: "New Owner" } });
  fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "owner@acme.example" } });
  fireEvent.change(screen.getByLabelText("Company name"), { target: { value: "Acme Commerce" } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "correct-horse-battery-staple" } });
  fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "correct-horse-battery-staple" } });
}

describe("SignupForm", () => {
  it("creates an owner workspace through the same-origin route", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}", { status: 201 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<SignupForm />);
    fillForm();
    expect(screen.getByLabelText("Workspace slug")).toHaveValue("acme-commerce");
    fireEvent.click(screen.getByRole("button", { name: "Create company workspace" }));

    await waitFor(() => expect(navigation.replace).toHaveBeenCalledWith("/dashboard"));
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(fetchMock.mock.calls[0][0]).toBe("/api/auth/register");
    expect(init.credentials).toBe("same-origin");
    expect(JSON.parse(String(init.body))).toEqual({
      display_name: "New Owner",
      email: "owner@acme.example",
      password: "correct-horse-battery-staple",
      organization_name: "Acme Commerce",
      organization_slug: "acme-commerce",
    });
  });

  it("rejects mismatched passwords before calling the API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<SignupForm />);
    fillForm();
    fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: "different-password-value" } });
    fireEvent.click(screen.getByRole("button", { name: "Create company workspace" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Passwords do not match");
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
