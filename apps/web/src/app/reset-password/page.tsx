import type { Metadata } from "next";
import Link from "next/link";
import { ResetPasswordForm } from "@/components/reset-password-form";
export const metadata: Metadata = { title: "Reset password" };
export default async function ResetPasswordPage({searchParams}:{searchParams:Promise<{token?:string}>}):Promise<React.ReactElement>{const {token}=await searchParams;return <main className="centered-state auth-page"><div className="login-card"><p className="eyebrow">SECURE PASSWORD RESET</p><h1>Choose a new password</h1><p className="muted">Completing this reset revokes every active session for the account.</p>{token?<ResetPasswordForm token={token}/>:<div className="form-error" role="alert">This password reset link is incomplete.</div>}<p className="auth-switch"><Link href="/forgot-password">Request another link</Link></p></div></main>}
