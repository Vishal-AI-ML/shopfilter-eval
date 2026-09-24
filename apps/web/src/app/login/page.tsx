import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { LoginForm } from "@/components/login-form";
import { getCurrentUser } from "@/lib/server-auth";

export const metadata: Metadata = { title: "Sign in" };

export default async function LoginPage(): Promise<React.ReactElement> {
  const user = await getCurrentUser();
  if (user) redirect("/dashboard");

  return (
    <main className="login-page">
      <section className="login-story">
        <div className="brand">
          <div className="brand-mark" aria-hidden="true">SF</div>
          <div>
            <strong>ShopFilter</strong>
            <span>Evaluation Console</span>
          </div>
        </div>
        <div className="story-copy">
          <p className="eyebrow">SEARCH QUALITY, PROVEN</p>
          <h1>Ship search changes with evidence—not intuition.</h1>
          <p>
            Evaluate relevance, filters, ranking and regressions against immutable
            datasets before customers see the change.
          </p>
        </div>
        <div className="signal-grid" aria-label="Platform capabilities">
          <div><strong>Deterministic</strong><span>Repeatable quality metrics</span></div>
          <div><strong>Traceable</strong><span>Case-level evidence</span></div>
          <div><strong>Durable</strong><span>Crash-safe execution</span></div>
        </div>
      </section>
      <section className="login-panel">
        <div className="login-card">
          <p className="eyebrow">WELCOME BACK</p>
          <h2>Sign in to your workspace</h2>
          <p className="muted">Sign in with your company account.</p>
          <LoginForm />
          <p className="auth-switch">New to ShopFilter? <Link href="/signup">Create a company workspace</Link></p>
        </div>
      </section>
    </main>
  );
}
