export type StaffRole = "admin" | "pos_user";
export type UserRole = StaffRole | "product_owner";
export type LanguagePref = "en" | "ta";

export interface User {
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

export interface UserCreate {
  name: string;
  email: string;
  phone?: string | null;
  password: string;
  role: StaffRole;
  store_id?: string | null;
  language_pref?: LanguagePref;
}

export interface UserUpdate {
  name?: string;
  phone?: string | null;
  store_id?: string | null;
  is_active?: boolean;
  language_pref?: LanguagePref;
}

export interface PlatformUserUpdate {
  name?: string;
  email?: string;
  phone?: string | null;
  is_active?: boolean;
}
