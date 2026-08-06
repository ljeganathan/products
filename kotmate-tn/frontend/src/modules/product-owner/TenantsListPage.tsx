import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { PLAN_LABELS } from "@/lib/constants";
import { cn } from "@/lib/utils";
import { listTenants } from "@/modules/product-owner/platformApi";

export function TenantsListPage() {
  const { data, isLoading, isError } = useQuery({ queryKey: ["tenants"], queryFn: listTenants });

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">Tenants</h1>
        <Link
          to="/platform/tenants/new"
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground"
        >
          + New Tenant
        </Link>
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {isError && <p className="text-sm text-chili">Failed to load tenants.</p>}

      {data && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-accent/5 text-left text-xs font-semibold uppercase tracking-wide text-foreground/60">
              <tr>
                <th className="px-3 py-2">Company</th>
                <th className="px-3 py-2">Code</th>
                <th className="px-3 py-2">Plan</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Users</th>
                <th className="px-3 py-2">Locations</th>
                <th className="px-3 py-2">Admin Login</th>
              </tr>
            </thead>
            <tbody>
              {data.map((tenant) => (
                <tr key={tenant.id} className="border-t border-border">
                  <td className="px-3 py-2 font-medium">
                    <Link to={`/platform/tenants/${tenant.id}`} className="hover:underline">
                      {tenant.company_name}
                    </Link>
                    {!tenant.is_active && (
                      <span className="ml-2 rounded-full bg-chili/10 px-2 py-0.5 text-xs text-chili">
                        Inactive
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-foreground/70">{tenant.tenant_code}</td>
                  <td className="px-3 py-2">
                    {tenant.plan_code ? PLAN_LABELS[tenant.plan_code] : "—"}
                  </td>
                  <td className="px-3 py-2">
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-semibold",
                        tenant.subscription_status === "active"
                          ? "bg-accent/10 text-accent"
                          : "bg-chili/10 text-chili",
                      )}
                    >
                      {tenant.subscription_status ?? "none"}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    {tenant.active_user_count} / {tenant.max_users ?? "∞"}
                  </td>
                  <td className="px-3 py-2">
                    {tenant.active_location_count} / {tenant.max_locations ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-foreground/70">{tenant.admin_login_id}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
