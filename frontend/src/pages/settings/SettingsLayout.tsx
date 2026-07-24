import { useTranslation } from "react-i18next";
import { NavLink, Outlet } from "react-router-dom";

import { cn } from "@/utils/cn";

const TABS = [
  { to: "/settings/tax", labelKey: "settings.navTax" },
  { to: "/settings/printer", labelKey: "settings.navPrinter" },
  { to: "/settings/company", labelKey: "settings.navCompany" },
  { to: "/settings/language", labelKey: "settings.navLanguage" },
  { to: "/settings/discounts", labelKey: "settings.navDiscounts" },
  { to: "/settings/subscription", labelKey: "settings.navSubscription" },
];

export default function SettingsLayout() {
  const { t } = useTranslation();

  return (
    <div className="flex flex-col gap-6">
      <h1 className="font-display text-2xl font-semibold text-slate-900">{t("settings.title")}</h1>

      <nav className="flex gap-1 overflow-x-auto border-b border-slate-200">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={({ isActive }) =>
              cn(
                "shrink-0 border-b-2 px-4 py-3 text-sm font-medium",
                isActive
                  ? "border-brand-600 text-brand-700"
                  : "border-transparent text-slate-500 hover:text-slate-800",
              )
            }
          >
            {t(tab.labelKey)}
          </NavLink>
        ))}
      </nav>

      <Outlet />
    </div>
  );
}
