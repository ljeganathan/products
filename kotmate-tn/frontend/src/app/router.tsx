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
import { InvoicesPage } from "@/modules/product-owner/InvoicesPage";
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

// AppShell wraps every non-POS/KOT tenant-scoped screen (Dashboard, Reports, Bill
// History, and every /admin/* master) so a persistent sidebar — not a per-page ad-hoc
// "← Dashboard" text link — is always the way back (Phase 15). /pos and /kot stay
// standalone on purpose: they're full-screen operational views (CLAUDE.md §9) that
// shouldn't compete with a sidebar for space.
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
      {
        path: "/reports",
        element: (
          <AppShell>
            <ReportsPage />
          </AppShell>
        ),
      },
      {
        path: "/billing/history",
        element: (
          <AppShell>
            <BillHistoryPage />
          </AppShell>
        ),
      },
    ],
  },
  {
    // Admin-only masters (Phase 04 Users, Phase 05 Categories/Items, Phase 06
    // Waiters/Sections/Tables, Phase 09 Tax/Discount Rules) — tenant_admin only,
    // CLAUDE.md §5.
    element: <ProtectedRoute roles={["tenant_admin"]} />,
    children: [
      {
        path: "/admin/users",
        element: (
          <AppShell>
            <UsersPage />
          </AppShell>
        ),
      },
      {
        path: "/admin/categories",
        element: (
          <AppShell>
            <CategoriesPage />
          </AppShell>
        ),
      },
      {
        path: "/admin/items",
        element: (
          <AppShell>
            <ItemsPage />
          </AppShell>
        ),
      },
      {
        path: "/admin/waiters",
        element: (
          <AppShell>
            <WaitersPage />
          </AppShell>
        ),
      },
      {
        path: "/admin/sections",
        element: (
          <AppShell>
            <SectionsPage />
          </AppShell>
        ),
      },
      {
        path: "/admin/tables",
        element: (
          <AppShell>
            <TablesPage />
          </AppShell>
        ),
      },
      {
        path: "/admin/printers",
        element: (
          <AppShell>
            <PrintersPage />
          </AppShell>
        ),
      },
      {
        path: "/admin/tax-rules",
        element: (
          <AppShell>
            <TaxRulesPage />
          </AppShell>
        ),
      },
      {
        path: "/admin/discount-rules",
        element: (
          <AppShell>
            <DiscountRulesPage />
          </AppShell>
        ),
      },
      {
        path: "/admin/settings",
        element: (
          <AppShell>
            <SettingsPage />
          </AppShell>
        ),
      },
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
          { path: "invoices", element: <InvoicesPage /> },
          { path: "plans", element: <PlansPage /> },
          { path: "maintenance", element: <MaintenancePage /> },
        ],
      },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);
