"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { errorMessage } from "@/lib/api-errors";

type State = "waiting" | "verifying" | "verified" | "error";

export function EmailVerificationPanel({ token, alreadyVerified = false }: { token?: string; alreadyVerified?: boolean }): React.ReactElement {
  const router = useRouter();
  const attempted = useRef(false);
  const [state, setState] = useState<State>(alreadyVerified ? "verified" : token ? "verifying" : "waiting");
  const [message, setMessage] = useState<string | null>(null);
  const [resending, setResending] = useState(false);

  useEffect(() => {
    if (!token || attempted.current) return;
    attempted.current = true;
    void (async () => {
      try {
        const response = await fetch("/api/auth/verify-email", {
          method: "POST",
          credentials: "same-origin",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ token }),
        });
        const body: unknown = await response.json().catch(() => null);
        if (!response.ok) {
          setMessage(errorMessage(body, "Unable to verify this email link."));
          setState("error");
          return;
        }
        setState("verified");
        router.replace("/verify-email?status=success");
        router.refresh();
      } catch {
        setMessage("Email verification service is unavailable. Please try again.");
        setState("error");
      }
    })();
  }, [router, token]);

  async function resend(): Promise<void> {
    setResending(true);
    setMessage(null);
    try {
      const response = await fetch("/api/auth/resend-verification", {
        method: "POST",
        credentials: "same-origin",
        headers: { "content-type": "application/json" },
        body: "{}",
      });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        setMessage(errorMessage(body, "Unable to send another verification link."));
        return;
      }
      setMessage("If verification is still required, a new link has been sent.");
    } catch {
      setMessage("Email verification service is unavailable. Please try again.");
    } finally {
      setResending(false);
    }
  }

  if (state === "verified") {
    return <><div className="form-success" role="status">Email verified. Your account is ready.</div><Link className="primary-button button-link" href="/dashboard">Continue to dashboard</Link></>;
  }
  return <>
    <div className={state === "error" ? "form-error" : "verification-note"} role="status">
      {state === "verifying" ? "Verifying your single-use link…" : message ?? "Open the verification link sent to your work email. The link is single-use and expires automatically."}
    </div>
    {state !== "verifying" ? <button className="secondary-button" type="button" disabled={resending} onClick={() => void resend()}>{resending ? "Sending…" : "Send another link"}</button> : null}
    <p className="auth-switch"><Link href="/dashboard">Return to dashboard</Link></p>
  </>;
}
