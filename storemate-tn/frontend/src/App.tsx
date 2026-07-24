import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { Toaster } from "@/components/ui/Toaster";
import { AppLayout } from "@/layouts/AppLayout";
import { PosLayout } from "@/layouts/PosLayout";
import CategoriesPage from "@/pages/CategoriesPage";
import DashboardPage from "@/pages/DashboardPage";
import ItemsPage from "@/pages/ItemsPage";
import LoginPage from "@/pages/auth/LoginPage";
import LowStockPage from "@/pages/LowStockPage";
import NotFoundPage from "@/pages/NotFoundPage";
import OwnerDashboardPage from "@/pages/owner/OwnerDashboardPage";
import OwnerInvoicesPage from "@/pages/owner/OwnerInvoicesPage";
import OwnerMaintenancePage from "@/pages/owner/OwnerMaintenancePage";
import OwnerPlansPage from "@/pages/owner/OwnerPlansPage";
import OwnerSubscriptionsPage from "@/pages/owner/OwnerSubscriptionsPage";
import OwnerTenantsPage from "@/pages/owner/OwnerTenantsPage";
import PosPage from "@/pages/PosPage";
import ReportsPage from "@/pages/ReportsPage";
import CompanySettingsPage from "@/pages/settings/CompanySettingsPage";
import DiscountRulesPage from "@/pages/settings/DiscountRulesPage";
import LanguageSettingsPage from "@/pages/settings/LanguageSettingsPage";
import PrinterSettingsPage from "@/pages/settings/PrinterSettingsPage";
import SettingsLayout from "@/pages/settings/SettingsLayout";
import SubscriptionSettingsPage from "@/pages/settings/SubscriptionSettingsPage";
import TaxSettingsPage from "@/pages/settings/TaxSettingsPage";
import StockPage from "@/pages/StockPage";
import UsersPage from "@/pages/UsersPage";
import { RequireAuth } from "@/routes/RequireAuth";
import { RequireRole } from "@/routes/RequireRole";
import { roleHomePath } from "@/routes/roleHome";
import { useAuthStore } from "@/store/authStore";

function RootRedirect() {
  const user = useAuthStore((s) => s.user);
  if (!user) return null; // RequireAuth (parent route) owns the signed-out case
  return <Navigate to={roleHomePath(user.role)} replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />

        <Route element={<RequireAuth />}>
          <Route path="/" element={<RootRedirect />} />

          {/* POS: dedicated full-viewport layout, no persistent sidebar. */}
          <Route element={<RequireRole allow={["admin", "pos_user"]} />}>
            <Route element={<PosLayout />}>
              <Route path="/pos" element={<PosPage />} />
            </Route>
          </Route>

          {/* Everything else: standard app shell (sidebar + topbar). */}
          <Route element={<AppLayout />}>
            <Route element={<RequireRole allow={["admin"]} />}>
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/items" element={<ItemsPage />} />
              <Route path="/categories" element={<CategoriesPage />} />
              <Route path="/users" element={<UsersPage />} />

              <Route path="/settings" element={<SettingsLayout />}>
                <Route index element={<Navigate to="tax" replace />} />
                <Route path="tax" element={<TaxSettingsPage />} />
                <Route path="printer" element={<PrinterSettingsPage />} />
                <Route path="company" element={<CompanySettingsPage />} />
                <Route path="language" element={<LanguageSettingsPage />} />
                <Route path="discounts" element={<DiscountRulesPage />} />
                <Route path="subscription" element={<SubscriptionSettingsPage />} />
              </Route>
            </Route>

            <Route element={<RequireRole allow={["admin", "pos_user"]} />}>
              <Route path="/stock" element={<StockPage />} />
              <Route path="/stock/low-stock" element={<LowStockPage />} />
              <Route path="/reports" element={<ReportsPage />} />
            </Route>

            <Route element={<RequireRole allow={["product_owner"]} />}>
              <Route path="/owner" element={<OwnerDashboardPage />} />
              <Route path="/owner/tenants" element={<OwnerTenantsPage />} />
              <Route path="/owner/plans" element={<OwnerPlansPage />} />
              <Route path="/owner/subscriptions" element={<OwnerSubscriptionsPage />} />
              <Route path="/owner/invoices" element={<OwnerInvoicesPage />} />
              <Route path="/owner/maintenance" element={<OwnerMaintenancePage />} />
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>

      <Toaster />
    </BrowserRouter>
  );
}
