import { Navigate, createBrowserRouter } from "react-router-dom";

import { AppShell } from "@/app/AppShell";
import { CategoriesPage } from "@/modules/admin/CategoriesPage";
import { DiscountRulesPage } from "@/modules/admin/DiscountRulesPage";
import { ItemsPage } from "@/modules/admin/ItemsPage";
import { PrintersPage } from "@/modules/admin/PrintersPage";
import { SectionsPage } from "@/modules/admin/SectionsPage";
import { SettingsPage } from "@/modules/admin/SettingsPage";
import { TablesPage } from "@/modules/admin/TablesPage";
import { TaxRulesPage } from "@/modules/admin/TaxRulesPage";
import { UsersPage } from "@/modules/admin/UsersPage";
import { WaitersPage } from "@/modules/admin/WaitersPage";
import { LoginPage } from "@/modules/auth/LoginPage";
import { ProtectedRoute } from "@/modules/auth/ProtectedRoute";
import { roleHomePath, useAuthStore } from "@/modules/auth/authStore";
import { BillHistoryPage } from "@/modules/billing/BillHistoryPage";
import { KotDisplayPage } from "@/modules/kot/KotDisplayPage";
import { POSPage } from "@/modules/pos/POSPage";
import { MaintenancePage } from "@/modules/product-owner/MaintenancePage";
import { PlansPage } from "@/modules/product-owner/PlansPage";
import { PlatformDashboardPage } from "@/modules/product-owner/PlatformDashboardPage";
import { PlatformShell } from "@/modules/product-owner/PlatformShell";
import { TenantCreatePage } from "@/modules/product-owner/TenantCreatePage";
import { TenantDetailPage } from "@/modules/product-owner/TenantDetailPage";
import { TenantsListPage } from "@/modules/product-owner/TenantsListPage";
import { DashboardPage } from "@/modules/reports/DashboardPage";
import { ReportsPage } from "@/modules/reports/ReportsPage";

function RootRedirect() {
  const accessToken = useAuthStore((state) => state.accessToken);
  const role = useAuthStore((state) => state.role);
  return <Navigate to={accessToken && role ? roleHomePath(role) : "/login"} replace />;
}

// AppShell is the shared Phase-00 placeholder shell for every tenant-scoped role
// until each phase builds out its own real screen — /pos, /kot, /billing/history,
// /dashboard, and /reports are now all real screens (Phases 07/08/09/11); nothing
// still routes to the bare placeholder.
//
// Each route gets its own role list rather than one shared group across every
// tenant-scoped path: a `kitchen` ("KOT User", CLAUDE.md §5) login must resolve only
// against /kot and nowhere else, and a `waiter` has POS access but — unlike
// pos_user/tenant_admin — no reports/dashboard access at all (CLAUDE.md §5: "no
// reports access" for waiters), so /dashboard and /reports deliberately exclude it
// even though /pos includes it.
export const router = createBrowserRouter([
  { path: "/", element: <RootRedirect /> },
  { path: "/login", element: <LoginPage /> },
  {
    element: <ProtectedRoute roles={["tenant_admin", "pos_user", "waiter"]} />,
    children: [{ path: "/pos", element: <POSPage /> }],
  },
  {
    element: <ProtectedRoute roles={["tenant_admin", "kitchen"]} />,
    children: [{ path: "/kot", element: <KotDisplayPage /> }],
  },
  {
    // Bill history/reprint (Phase 09), Dashboard + Reports (Phase 11) — cashier +
    // admin only, never waiter.
    element: <ProtectedRoute roles={["tenant_admin", "pos_user"]} />,
    children: [
      {
        path: "/dashboard",
        element: (
          <AppShell>
            <DashboardPage />
          </AppShell>
        ),
      },
      { path: "/reports", element: <ReportsPage /> },
      { path: "/billing/history", element: <BillHistoryPage /> },
    ],
  },
  {
    // Admin-only masters (Phase 04 Users, Phase 05 Categories/Items, Phase 06
    // Waiters/Sections/Tables, Phase 09 Tax/Discount Rules) — tenant_admin only,
    // CLAUDE.md §5.
    element: <ProtectedRoute roles={["tenant_admin"]} />,
    children: [
      { path: "/admin/users", element: <UsersPage /> },
      { path: "/admin/categories", element: <CategoriesPage /> },
      { path: "/admin/items", element: <ItemsPage /> },
      { path: "/admin/waiters", element: <WaitersPage /> },
      { path: "/admin/sections", element: <SectionsPage /> },
      { path: "/admin/tables", element: <TablesPage /> },
      { path: "/admin/printers", element: <PrintersPage /> },
      { path: "/admin/tax-rules", element: <TaxRulesPage /> },
      { path: "/admin/discount-rules", element: <DiscountRulesPage /> },
      { path: "/admin/settings", element: <SettingsPage /> },
    ],
  },
  {
    element: <ProtectedRoute roles={["product_owner"]} />,
    children: [
      {
        path: "/platform",
        element: <PlatformShell />,
        children: [
          { index: true, element: <PlatformDashboardPage /> },
          { path: "tenants", element: <TenantsListPage /> },
          { path: "tenants/new", element: <TenantCreatePage /> },
          { path: "tenants/:tenantId", element: <TenantDetailPage /> },
          { path: "plans", element: <PlansPage /> },
          { path: "maintenance", element: <MaintenancePage /> },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
