import type { Metadata } from "next";
import Link from "next/link";
import { getCurrentUser } from "@/lib/server-auth";

export const metadata: Metadata = { title: "Overview" };

export default async function DashboardPage(): Promise<React.ReactElement> {
  const user = await getCurrentUser();
  return (
    <div className="dashboard-stack">
      {user && !user.email_verified ? <section className="verification-banner"><div><strong>Verify your work email</strong><span>Required before sensitive organization and team actions.</span></div><Link href="/verify-email">Verify now</Link></section> : null}
      <section className="page-heading">
        <div>
          <p className="eyebrow">CONTROL PLANE</p>
          <h1>Search quality workspace</h1>
          <p>Authenticated shell connected to the canonical ShopFilter API.</p>
        </div>
        <div className="status-pill"><span /> API session active</div>
      </section>

      <section className="foundation-card">
        <div className="foundation-icon">01</div>
        <div>
          <p className="eyebrow">PHASE 17 · FOUNDATION</p>
          <h2>Your secure operator console is ready.</h2>
          <p>
            Authentication, protected routing, role-aware navigation and session
            restoration are now in place. Product workflows will be added one
            verified checkpoint at a time.
          </p>
        </div>
      </section>

      <section className="module-grid" aria-label="Upcoming product modules">
        <article><span>01</span><h3>Projects</h3><p>Scope catalogs, datasets and search systems by tenant.</p><small>Next checkpoint</small></article>
        <article><span>02</span><h3>Evaluation runs</h3><p>Start durable jobs and monitor live progress.</p><small>Planned</small></article>
        <article><span>03</span><h3>Failure explorer</h3><p>Inspect expected versus actual results with evidence.</p><small>Planned</small></article>
        <article><span>04</span><h3>Regression</h3><p>Compare immutable baseline and candidate versions.</p><small>Planned</small></article>
      </section>

      <section className="principles-row">
        <div><strong>No fabricated impact</strong><span>Evidence before inference</span></div>
        <div><strong>Immutable versions</strong><span>Reproducible evaluation</span></div>
        <div><strong>Deterministic first</strong><span>Optional judgment later</span></div>
      </section>
    </div>
  );
}
