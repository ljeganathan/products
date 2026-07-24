import {
  AlertOctagon,
  Boxes,
  Building2,
  CreditCard,
  FileBarChart2,
  FileText,
  LayoutDashboard,
  type LucideIcon,
  Package,
  Repeat,
  Settings,
  ShoppingCart,
  Tags,
  Users,
} from "lucide-react";

import type { UserRole } from "@/types/auth";

export interface NavItem {
  to: string;
  labelKey: string;
  icon: LucideIcon;
}

const ADMIN_NAV: NavItem[] = [
  { to: "/dashboard", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { to: "/pos", labelKey: "nav.pos", icon: ShoppingCart },
  { to: "/stock", labelKey: "nav.stock", icon: Boxes },
  { to: "/items", labelKey: "nav.items", icon: Package },
  { to: "/categories", labelKey: "nav.categories", icon: Tags },
  { to: "/reports", labelKey: "nav.reports", icon: FileBarChart2 },
  { to: "/users", labelKey: "nav.users", icon: Users },
  { to: "/settings", labelKey: "nav.settings", icon: Settings },
];

const POS_USER_NAV: NavItem[] = [
  { to: "/pos", labelKey: "nav.pos", icon: ShoppingCart },
  { to: "/stock", labelKey: "nav.stock", icon: Boxes },
  { to: "/reports", labelKey: "nav.reports", icon: FileBarChart2 },
];

const PRODUCT_OWNER_NAV: NavItem[] = [
  { to: "/owner", labelKey: "nav.platformDashboard", icon: LayoutDashboard },
  { to: "/owner/tenants", labelKey: "nav.tenants", icon: Building2 },
  { to: "/owner/plans", labelKey: "nav.plans", icon: CreditCard },
  { to: "/owner/subscriptions", labelKey: "nav.subscriptions", icon: Repeat },
  { to: "/owner/invoices", labelKey: "nav.invoices", icon: FileText },
  { to: "/owner/maintenance", labelKey: "nav.maintenance", icon: AlertOctagon },
];

export function navItemsForRole(role: UserRole): NavItem[] {
  switch (role) {
    case "admin":
      return ADMIN_NAV;
    case "pos_user":
      return POS_USER_NAV;
    case "product_owner":
      return PRODUCT_OWNER_NAV;
    default:
      return [];
  }
}
