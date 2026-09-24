export type MembershipRole =
  | "OWNER"
  | "ADMIN"
  | "ENGINEER"
  | "REVIEWER"
  | "VIEWER";

export interface Membership {
  organization_id: string;
  role: MembershipRole;
}

export interface AuthenticatedUser {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  memberships: Membership[];
}

export interface LoginResponse {
  user: AuthenticatedUser;
  expires_at: string;
}
