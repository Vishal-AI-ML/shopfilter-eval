"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function LogoutButton(): React.ReactElement {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function logout(): Promise<void> {
    setPending(true);
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        credentials: "same-origin",
      });
    } finally {
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <button className="logout-button" type="button" onClick={logout} disabled={pending}>
      {pending ? "Signing out…" : "Sign out"}
    </button>
  );
}
