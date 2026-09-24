import type { Metadata } from "next";
import { AcceptInvitationForm } from "@/components/accept-invitation-form";
export const metadata: Metadata = { title: "Accept invitation", referrer: "no-referrer" };
export default async function AcceptInvitationPage({ searchParams }: { searchParams: Promise<{ token?: string }> }): Promise<React.ReactElement> { const { token } = await searchParams; return <main className="centered-state auth-page"><div className="login-card"><p className="eyebrow">ORGANIZATION INVITATION</p><h1>Join your ShopFilter team</h1><p className="muted">Accept this single-use invitation to access the organization.</p>{token ? <AcceptInvitationForm token={token} /> : <div className="form-error" role="alert">This invitation link is incomplete.</div>}</div></main>; }
