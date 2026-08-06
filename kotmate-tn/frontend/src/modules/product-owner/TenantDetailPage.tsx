import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { PLAN_LABELS } from "@/lib/constants";
import {
  changeTenantPlan,
  getTenant,
  updateSubscriptionStatus,
  updateTenant,
} from "@/modules/product-owner/platformApi";

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-foreground/60">{label}</p>
      <p className="mt-0.5 text-sm">{value || "—"}</p>
    </div>
  );
}

export function TenantDetailPage() {
  const { tenantId } = useParams<{ tenantId: string }>();
  const queryClient = useQueryClient();
  const [planCode, setPlanCode] = useState("");
  const [billingCycle, setBillingCycle] = useState("monthly");

  const { data: tenant, isLoading } = useQuery({
    queryKey: ["tenant", tenantId],
    queryFn: () => getTenant(tenantId!),
    enabled: !!tenantId,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["tenant", tenantId] });
    void queryClient.invalidateQueries({ queryKey: ["tenants"] });
  };

  const planMutation = useMutation({
    mutationFn: () => changeTenantPlan(tenantId!, planCode, billingCycle),
    onSuccess: invalidate,
  });
  const statusMutation = useMutation({
    mutationFn: (status: string) => updateSubscriptionStatus(tenantId!, status),
    onSuccess: invalidate,
  });
  const activeMutation = useMutation({
    mutationFn: (is_active: boolean) => updateTenant(tenantId!, { is_active }),
    onSuccess: invalidate,
  });

  if (isLoading || !tenant) return <p className="text-sm text-foreground/60">Loading…</p>;

  return (
    <div className="max-w-2xl">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">{tenant.company_name}</h1>
          <p className="text-sm text-foreground/60">
            {tenant.tenant_code} · Admin login: {tenant.admin_login_id}
          </p>
        </div>
        <button
          type="button"
          onClick={() => activeMutation.mutate(!tenant.is_active)}
          className="rounded-md border border-border px-3 py-1.5 text-xs font-semibold hover:bg-accent/10"
        >
          {tenant.is_active ? "Deactivate" : "Reactivate"}
        </button>
      </div>

      <div className="grid grid-cols-2 gap-4 rounded-lg border border-border p-4">
        <Field
          label="Address"
          value={[tenant.door_no, tenant.street, tenant.city, tenant.district, tenant.state, tenant.pincode]
            .filter(Boolean)
            .join(", ")}
        />
        <Field label="Plan" value={tenant.plan_code ? PLAN_LABELS[tenant.plan_code] : "—"} />
        <Field label="Subscription Status" value={tenant.subscription_status ?? "—"} />
        <Field label="Billing Cycle" value={tenant.billing_cycle ?? "—"} />
        <Field
          label="Current Period"
          value={
            tenant.current_period_start && tenant.current_period_end
              ? `${tenant.current_period_start} → ${tenant.current_period_end}`
              : "—"
          }
        />
        <Field label="Seat Usage" value={`${tenant.active_user_count} / ${tenant.max_users ?? "∞"}`} />
        <Field
          label="Location Usage"
          value={`${tenant.active_location_count} / ${tenant.max_locations ?? "—"}`}
        />
      </div>

      <div className="mt-6 rounded-lg border border-border p-4">
        <h2 className="mb-3 text-sm font-semibold">Change Plan</h2>
        <div className="flex items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-foreground/70">Plan</label>
            <select
              className="min-h-10 rounded-md border border-border bg-background px-3 text-sm"
              value={planCode || tenant.plan_code || "lite"}
              onChange={(e) => setPlanCode(e.target.value)}
            >
              <option value="lite">Lite</option>
              <option value="pro">Pro</option>
              <option value="pro_max">Pro Max</option>
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-foreground/70">Billing Cycle</label>
            <select
              className="min-h-10 rounded-md border border-border bg-background px-3 text-sm"
              value={billingCycle}
              onChange={(e) => setBillingCycle(e.target.value)}
            >
              <option value="monthly">Monthly</option>
              <option value="yearly">Yearly</option>
            </select>
          </div>
          <button
            type="button"
            disabled={planMutation.isPending}
            onClick={() => planMutation.mutate()}
            className="min-h-10 rounded-md bg-accent px-4 text-sm font-semibold text-accent-foreground disabled:opacity-60"
          >
            {planMutation.isPending ? "Applying…" : "Apply"}
          </button>
        </div>
      </div>

      <div className="mt-6 rounded-lg border border-border p-4">
        <h2 className="mb-3 text-sm font-semibold">Subscription Status</h2>
        <div className="flex gap-2">
          {["active", "suspended", "cancelled"].map((status) => (
            <button
              key={status}
              type="button"
              disabled={statusMutation.isPending || tenant.subscription_status === status}
              onClick={() => statusMutation.mutate(status)}
              className="rounded-md border border-border px-3 py-1.5 text-xs font-semibold capitalize hover:bg-accent/10 disabled:opacity-40"
            >
              {status}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
