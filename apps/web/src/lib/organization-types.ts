import type { MembershipRole } from "@/lib/auth-types";

export interface OrganizationMember {
  id: string;
  organization_id: string;
  user_id: string;
  email: string;
  display_name: string;
  role: MembershipRole;
  created_at: string;
}

export interface OrganizationInvitation {
  id: string;
  organization_id: string;
  email: string;
  role: MembershipRole;
  expires_at: string;
  created_at: string;
}
