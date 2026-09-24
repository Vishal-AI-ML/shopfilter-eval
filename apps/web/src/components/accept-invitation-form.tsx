"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { errorMessage } from "@/lib/api-errors";

export function AcceptInvitationForm({ token }: { token: string }): React.ReactElement {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault(); setError(null);
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") ?? "");
    setPending(true);
    try {
      const response = await fetch("/api/auth/accept-invitation", { method: "POST", credentials: "same-origin", headers: { "content-type": "application/json" }, body: JSON.stringify({ token, display_name: String(form.get("display_name") ?? "") || null, password }) });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) { setError(errorMessage(body, "Unable to accept this invitation.")); return; }
      router.replace("/dashboard"); router.refresh();
    } catch { setError("Invitation service is unavailable. Please try again."); }
    finally { setPending(false); }
  }
  return <form className="login-form" onSubmit={submit}><div className="field"><label htmlFor="display_name">Your name <span className="muted">(new accounts)</span></label><input id="display_name" name="display_name" maxLength={200} autoComplete="name" /></div><div className="field"><label htmlFor="password">Account password</label><input id="password" name="password" type="password" minLength={12} maxLength={1024} required autoComplete="current-password" /></div>{error ? <div className="form-error" role="alert">{error}</div> : null}<button className="primary-button" disabled={pending}>{pending ? "Accepting…" : "Accept invitation"}</button><p className="security-note">Existing users confirm their password. New users create a password and prove email ownership through this single-use link.</p></form>;
}
