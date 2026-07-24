export type UserRole = "product_owner" | "admin" | "pos_user";

export type LanguagePref = "en" | "ta";

export interface AuthUser {
  id: string;
  tenant_id: string | null;
  store_id: string | null;
  name: string;
  email: string;
  phone: string | null;
  role: UserRole;
  is_active: boolean;
  language_pref: LanguagePref;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  user: AuthUser;
}

export interface AccessTokenResponse {
  access_token: string;
}
