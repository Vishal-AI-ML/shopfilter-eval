import type { MembershipRole } from "@/lib/auth-types";

export type Capability =
  | "view"
  | "execute_evaluation"
  | "review_dataset"
  | "manage_members";

const capabilities: Record<MembershipRole, ReadonlySet<Capability>> = {
  OWNER: new Set(["view", "execute_evaluation", "review_dataset", "manage_members"]),
  ADMIN: new Set(["view", "execute_evaluation", "review_dataset", "manage_members"]),
  ENGINEER: new Set(["view", "execute_evaluation"]),
  REVIEWER: new Set(["view", "review_dataset"]),
  VIEWER: new Set(["view"]),
};

export function can(role: MembershipRole, capability: Capability): boolean {
  return capabilities[role].has(capability);
}
