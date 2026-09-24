import type { Metadata } from "next";

import { EmailVerificationPanel } from "@/components/email-verification-panel";

export const metadata: Metadata = { title: "Verify email", referrer: "no-referrer" };

export default async function VerifyEmailPage({ searchParams }: { searchParams: Promise<{ token?: string; status?: string }> }): Promise<React.ReactElement> {
  const { token, status } = await searchParams;
  return <main className="centered-state auth-page"><div className="login-card"><p className="eyebrow">EMAIL OWNERSHIP</p><h1>{status === "success" ? "Email verified" : "Verify your work email"}</h1><p className="muted">Verification protects organization membership and other sensitive team actions.</p><EmailVerificationPanel token={token} alreadyVerified={status === "success"} /></div></main>;
}
