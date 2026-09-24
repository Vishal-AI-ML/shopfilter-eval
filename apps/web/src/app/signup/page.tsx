import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { SignupForm } from "@/components/signup-form";
import { getCurrentUser } from "@/lib/server-auth";

export const metadata: Metadata = { title: "Create workspace" };

export default async function SignupPage(): Promise<React.ReactElement> {
  const user = await getCurrentUser();
  if (user) redirect("/dashboard");

  return (
    <main className="login-page">
      <section className="login-story">
        <div className="brand"><div className="brand-mark" aria-hidden="true">SF</div><div><strong>ShopFilter</strong><span>Evaluation Console</span></div></div>
        <div className="story-copy">
          <p className="eyebrow">CREATE YOUR COMPANY WORKSPACE</p>
          <h1>Make search quality measurable from day one.</h1>
          <p>Start an isolated organization for your team, catalogs, golden datasets and evaluation evidence.</p>
        </div>
        <div className="signal-grid" aria-label="Workspace guarantees">
          <div><strong>Isolated</strong><span>Tenant-scoped company data</span></div>
          <div><strong>Controlled</strong><span>Owner-led team access</span></div>
          <div><strong>Reproducible</strong><span>Immutable evaluation evidence</span></div>
        </div>
      </section>
      <section className="login-panel">
        <div className="login-card signup-card">
          <p className="eyebrow">GET STARTED</p>
          <h2>Create your workspace</h2>
          <p className="muted">Create the first Owner account for your company.</p>
          <SignupForm />
          <p className="auth-switch">Already have an account? <Link href="/login">Sign in</Link></p>
        </div>
      </section>
    </main>
  );
}
