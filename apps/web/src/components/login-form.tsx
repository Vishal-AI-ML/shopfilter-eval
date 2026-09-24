"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { errorMessage } from "@/lib/api-errors";

export function LoginForm(): React.ReactElement {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          email: String(form.get("email") ?? ""),
          password: String(form.get("password") ?? ""),
        }),
      });

      if (!response.ok) {
        const body: unknown = await response.json().catch(() => null);
        setError(errorMessage(body, "Unable to sign in. Please try again."));
        return;
      }

      router.replace("/dashboard");
      router.refresh();
    } catch {
      setError("Authentication service is unavailable. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="login-form" onSubmit={submit}>
      <div className="field">
        <label htmlFor="email">Work email</label>
        <input
          id="email"
          name="email"
          type="email"
          autoComplete="username"
          required
          maxLength={320}
          placeholder="you@company.com"
        />
      </div>
      <div className="field">
        <div className="label-row">
          <label htmlFor="password">Password</label>
          <span>Stored only by your password manager</span>
        </div>
        <input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          maxLength={1024}
          placeholder="Enter your password"
        />
      </div>
      {error ? <div className="form-error" role="alert">{error}</div> : null}
      <button className="primary-button" type="submit" disabled={submitting}>
        {submitting ? "Signing in…" : "Sign in securely"}
      </button>
      <p className="security-note">
        Session authentication uses an HttpOnly cookie. Credentials are never
        stored in browser storage.
      </p>
    </form>
  );
}
