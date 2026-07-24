import type { UserRole } from "@/types/auth";

/** Default landing route per role — used both after login and when a role
 * guard redirects a signed-in user away from a screen they can't access. */
export function roleHomePath(role: UserRole): string {
  switch (role) {
    case "product_owner":
      return "/owner";
    case "admin":
      return "/dashboard";
    case "pos_user":
      return "/pos";
    default:
      return "/login";
  }
}
