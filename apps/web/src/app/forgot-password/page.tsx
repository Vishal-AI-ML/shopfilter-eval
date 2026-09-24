import type { Metadata } from "next";
import Link from "next/link";
import { ForgotPasswordForm } from "@/components/forgot-password-form";
export const metadata: Metadata = { title: "Forgot password" };
export default function ForgotPasswordPage(): React.ReactElement {
 return <main className="centered-state auth-page"><div className="login-card"><p className="eyebrow">ACCOUNT RECOVERY</p><h1>Reset your password</h1><p className="muted">Enter your work email. The response is intentionally identical whether or not an account exists.</p><ForgotPasswordForm /><p className="auth-switch"><Link href="/login">Return to sign in</Link></p></div></main>;
}
