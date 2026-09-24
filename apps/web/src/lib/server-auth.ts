import "server-only";

import { cookies } from "next/headers";

import type { AuthenticatedUser } from "@/lib/auth-types";

const DEFAULT_API_URL = "http://localhost:8000";

export function apiBaseUrl(): string {
  const value = process.env.SHOPFILTER_API_INTERNAL_URL ?? DEFAULT_API_URL;
  const url = new URL(value);

  if (!['http:', 'https:'].includes(url.protocol)) {
    throw new Error("SHOPFILTER_API_INTERNAL_URL must use http or https");
  }

  return url.origin;
}

export async function getCurrentUser(): Promise<AuthenticatedUser | null> {
  const cookieStore = await cookies();
  const response = await fetch(`${apiBaseUrl()}/v1/auth/me`, {
    headers: {
      cookie: cookieStore.toString(),
    },
    cache: "no-store",
  });

  if (response.status === 401) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Authentication service returned HTTP ${response.status}`);
  }
  return (await response.json()) as AuthenticatedUser;
}
