/** `*_limit === -1` means unlimited, matching the backend's UNLIMITED sentinel. */
export interface Usage {
  users_count: number;
  users_limit: number;
  stores_count: number;
  stores_limit: number;
  printer_profiles_count: number;
  printer_profiles_limit: number;
}
