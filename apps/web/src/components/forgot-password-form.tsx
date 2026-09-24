"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { errorMessage } from "@/lib/api-errors";

export function ForgotPasswordForm(): React.ReactElement {
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault(); setError(null); setPending(true);
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/auth/forgot-password", {
        method: "POST", credentials: "same-origin",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: String(form.get("email") ?? "") }),
      });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) { setError(errorMessage(body, "Unable to process the request.")); return; }
      setMessage("If that account exists, a password reset link has been sent.");
    } catch { setError("Password reset service is unavailable. Please try again."); }
    finally { setPending(false); }
  }

  if (message) return <div className="success-state" role="status"><strong>Check your email</strong><p>{message}</p><Link href="/login">Return to sign in</Link></div>;
  return <form className="login-form" onSubmit={submit}>
    <div className="field"><label htmlFor="email">Work email</label><input id="email" name="email" type="email" autoComplete="email" required maxLength={320} placeholder="you@company.com" /></div>
    {error ? <div className="form-error" role="alert">{error}</div> : null}
    <button className="primary-button" type="submit" disabled={pending}>{pending ? "Sending…" : "Send reset link"}</button>
  </form>;
}
