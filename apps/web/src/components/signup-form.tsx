"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { errorMessage } from "@/lib/api-errors";

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 100);
}

export function SignupForm(): React.ReactElement {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setError(null);
    const form = new FormData(event.currentTarget);
    const password = String(form.get("password") ?? "");
    const confirmation = String(form.get("password_confirmation") ?? "");
    if (password !== confirmation) {
      setError("Passwords do not match.");
      return;
    }

    setSubmitting(true);
    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        credentials: "same-origin",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          display_name: String(form.get("display_name") ?? ""),
          email: String(form.get("email") ?? ""),
          password,
          organization_name: String(form.get("organization_name") ?? ""),
          organization_slug: String(form.get("organization_slug") ?? ""),
        }),
      });

      if (!response.ok) {
        const body: unknown = await response.json().catch(() => null);
        setError(errorMessage(body, "Unable to create the workspace. Please try again."));
        return;
      }

      router.replace("/verify-email");
      router.refresh();
    } catch {
      setError("Registration service is unavailable. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="login-form" onSubmit={submit}>
      <div className="form-grid">
        <div className="field full-field">
          <label htmlFor="display_name">Your name</label>
          <input id="display_name" name="display_name" required maxLength={200} autoComplete="name" placeholder="Vishal Shivhare" />
        </div>
        <div className="field full-field">
          <label htmlFor="email">Work email</label>
          <input id="email" name="email" type="email" required maxLength={320} autoComplete="email" placeholder="you@company.com" />
        </div>
        <div className="field">
          <label htmlFor="organization_name">Company name</label>
          <input
            id="organization_name"
            name="organization_name"
            required
            maxLength={200}
            autoComplete="organization"
            placeholder="Acme Commerce"
            onChange={(event) => {
              if (!slugEdited) setSlug(slugify(event.currentTarget.value));
            }}
          />
        </div>
        <div className="field">
          <label htmlFor="organization_slug">Workspace slug</label>
          <input
            id="organization_slug"
            name="organization_slug"
            required
            minLength={1}
            maxLength={100}
            pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
            value={slug}
            placeholder="acme-commerce"
            onChange={(event) => {
              setSlugEdited(true);
              setSlug(slugify(event.currentTarget.value));
            }}
          />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input id="password" name="password" type="password" required minLength={12} maxLength={1024} autoComplete="new-password" placeholder="At least 12 characters" />
        </div>
        <div className="field">
          <label htmlFor="password_confirmation">Confirm password</label>
          <input id="password_confirmation" name="password_confirmation" type="password" required minLength={12} maxLength={1024} autoComplete="new-password" placeholder="Repeat your password" />
        </div>
      </div>
      {error ? <div className="form-error" role="alert">{error}</div> : null}
      <button className="primary-button" type="submit" disabled={submitting}>
        {submitting ? "Creating workspace…" : "Create company workspace"}
      </button>
      <p className="security-note">You become the first Owner. Your password is sent only to the secure API and is never stored by the web interface.</p>
    </form>
  );
}
