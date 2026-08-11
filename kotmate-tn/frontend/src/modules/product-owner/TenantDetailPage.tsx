import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { useState } from "react";
import { useParams } from "react-router-dom";

import { INDIAN_STATES, PLAN_LABELS } from "@/lib/constants";
import {
  changeTenantPlan,
  getTenant,
  resetTenantAdminPassword,
  type TenantDetail,
  updateSubscriptionPeriod,
  updateSubscriptionStatus,
  updateTenant,
} from "@/modules/product-owner/platformApi";

// Mirrors the Dashboard's expiring-subscriptions alert and the Tenants list's own copy
// of this logic (TenantsListPage.tsx) — red once lapsed, gold inside the 7-day window.
function daysRemaining(currentPeriodEnd: string): number {
  const msPerDay = 24 * 60 * 60 * 1000;
  const end = new Date(`${currentPeriodEnd}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((end.getTime() - today.getTime()) / msPerDay);
}

function Field({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-foreground/60">{label}</p>
      <p className="mt-0.5 text-sm">{value || "—"}</p>
    </div>
  );
}

type EditableTenantFields = Pick<
  TenantDetail,
  "company_name" | "email" | "phone" | "door_no" | "street" | "city" | "district" | "state" | "pincode"
>;

function toEditForm(tenant: TenantDetail): EditableTenantFields {
  return {
    company_name: tenant.company_name,
    email: tenant.email,
    phone: tenant.phone,
    door_no: tenant.door_no,
    street: tenant.street,
    city: tenant.city,
    district: tenant.district,
    state: tenant.state,
    pincode: tenant.pincode,
  };
}

const inputClass =
  "min-h-9 rounded-md border border-border bg-background px-2.5 text-sm outline-none focus:ring-2 focus:ring-accent";
const labelClass = "text-xs font-medium text-foreground/70";

export function TenantDetailPage() {
  const { tenantId } = useParams<{ tenantId: string }>();
  const queryClient = useQueryClient();
  const [planCode, setPlanCode] = useState("");
  const [billingCycle, setBillingCycle] = useState("monthly");
  const [expiryDate, setExpiryDate] = useState("");
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState<EditableTenantFields | null>(null);
  const [resetResult, setResetResult] = useState<{ admin_login_id: string; temp_password: string } | null>(
    null,
  );

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
  const periodMutation = useMutation({
    mutationFn: () => updateSubscriptionPeriod(tenantId!, expiryDate),
    onSuccess: () => {
      invalidate();
      setExpiryDate("");
    },
  });
  const activeMutation = useMutation({
    mutationFn: (is_active: boolean) => updateTenant(tenantId!, { is_active }),
    onSuccess: invalidate,
  });
  const editMutation = useMutation({
    mutationFn: (payload: EditableTenantFields) => updateTenant(tenantId!, payload),
    onSuccess: () => {
      invalidate();
      setIsEditing(false);
    },
  });
  const resetPasswordMutation = useMutation({
    mutationFn: () => resetTenantAdminPassword(tenantId!),
    onSuccess: setResetResult,
  });

  if (isLoading || !tenant) return <p className="text-sm text-foreground/60">Loading…</p>;

  function startEditing() {
    setEditForm(toEditForm(tenant!));
    setIsEditing(true);
  }

  function updateField<K extends keyof EditableTenantFields>(key: K, value: EditableTenantFields[K]) {
    setEditForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold">{tenant.company_name}</h1>
          <p className="text-sm text-foreground/60">
            {tenant.tenant_code} · Admin login: {tenant.admin_login_id}
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => resetPasswordMutation.mutate()}
            disabled={resetPasswordMutation.isPending}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-semibold hover:bg-accent/10 disabled:opacity-60"
          >
            {resetPasswordMutation.isPending ? "Resetting…" : "Reset Admin Password"}
          </button>
          <button
            type="button"
            onClick={() => activeMutation.mutate(!tenant.is_active)}
            className="rounded-md border border-border px-3 py-1.5 text-xs font-semibold hover:bg-accent/10"
          >
            {tenant.is_active ? "Deactivate" : "Reactivate"}
          </button>
        </div>
      </div>

      {resetResult && (
        <div className="mb-4 rounded-lg border border-accent bg-accent/10 p-4 text-sm">
          <p className="font-semibold">
            New password for {resetResult.admin_login_id}: <code>{resetResult.temp_password}</code>
          </p>
          <p className="mt-1 text-xs text-foreground/60">
            Shown once — hand this to the tenant admin now. It will not be shown again.
          </p>
          <button
            type="button"
            onClick={() => setResetResult(null)}
            className="mt-2 text-xs font-semibold underline"
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="rounded-lg border border-border p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">Company Master</h2>
          {!isEditing && (
            <button
              type="button"
              onClick={startEditing}
              className="text-xs font-semibold text-accent hover:underline"
            >
              Edit
            </button>
          )}
        </div>

        {!isEditing ? (
          <div className="grid grid-cols-2 gap-4">
            <Field label="Email" value={tenant.email ?? ""} />
            <Field label="Phone" value={tenant.phone ?? ""} />
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
        ) : (
          editForm && (
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-1.5">
                <label className={labelClass}>Company Name</label>
                <input
                  className={inputClass}
                  value={editForm.company_name}
                  onChange={(e) => updateField("company_name", e.target.value)}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="flex flex-col gap-1.5">
                  <label className={labelClass}>Email</label>
                  <input
                    type="email"
                    className={inputClass}
                    value={editForm.email ?? ""}
                    onChange={(e) => updateField("email", e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className={labelClass}>Phone</label>
                  <input
                    type="tel"
                    className={inputClass}
                    value={editForm.phone ?? ""}
                    onChange={(e) => updateField("phone", e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className={labelClass}>Door No.</label>
                  <input
                    className={inputClass}
                    value={editForm.door_no ?? ""}
                    onChange={(e) => updateField("door_no", e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className={labelClass}>Street / Area</label>
                  <input
                    className={inputClass}
                    value={editForm.street ?? ""}
                    onChange={(e) => updateField("street", e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className={labelClass}>City</label>
                  <input
                    className={inputClass}
                    value={editForm.city ?? ""}
                    onChange={(e) => updateField("city", e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className={labelClass}>District</label>
                  <input
                    className={inputClass}
                    value={editForm.district ?? ""}
                    onChange={(e) => updateField("district", e.target.value)}
                  />
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className={labelClass}>State</label>
                  <select
                    className={inputClass}
                    value={editForm.state ?? ""}
                    onChange={(e) => updateField("state", e.target.value)}
                  >
                    {INDIAN_STATES.map((s) => (
                      <option key={s} value={s}>
                        {s}
                      </option>
                    ))}
                  </select>
                </div>
                <div className="flex flex-col gap-1.5">
                  <label className={labelClass}>PIN Code</label>
                  <input
                    pattern="[1-9][0-9]{5}"
                    className={inputClass}
                    value={editForm.pincode ?? ""}
                    onChange={(e) => updateField("pincode", e.target.value)}
                  />
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={editMutation.isPending}
                  onClick={() => editMutation.mutate(editForm)}
                  className="rounded-md bg-accent px-4 py-1.5 text-xs font-semibold text-accent-foreground disabled:opacity-60"
                >
                  {editMutation.isPending ? "Saving…" : "Save"}
                </button>
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="rounded-md border border-border px-4 py-1.5 text-xs font-semibold hover:bg-accent/10"
                >
                  Cancel
                </button>
              </div>
            </div>
          )
        )}
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
        <h2 className="mb-3 text-sm font-semibold">Plan Expiry Date</h2>
        <p className="mb-3 text-xs text-foreground/60">
          Manually renew or correct this tenant's expiry date without changing their plan — a fresh
          full-length period is set automatically whenever a plan change is applied above.
        </p>
        <div className="mb-3 flex items-center gap-2 text-sm">
          <span className="text-foreground/60">Current:</span>
          {tenant.current_period_end ? (
            <span
              className={
                daysRemaining(tenant.current_period_end) < 0
                  ? "font-semibold text-chili"
                  : daysRemaining(tenant.current_period_end) <= 7
                    ? "font-semibold text-gold"
                    : "font-medium"
              }
            >
              {tenant.current_period_end}
              {daysRemaining(tenant.current_period_end) < 0
                ? ` (expired ${-daysRemaining(tenant.current_period_end)}d ago)`
                : daysRemaining(tenant.current_period_end) <= 7
                  ? ` (${daysRemaining(tenant.current_period_end)}d left)`
                  : ""}
            </span>
          ) : (
            <span className="text-foreground/40">— no active subscription</span>
          )}
        </div>
        <div className="flex items-end gap-3">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-foreground/70">New Expiry Date</label>
            <input
              type="date"
              className="min-h-10 rounded-md border border-border bg-background px-3 text-sm"
              value={expiryDate}
              onChange={(e) => setExpiryDate(e.target.value)}
            />
          </div>
          <button
            type="button"
            disabled={periodMutation.isPending || !expiryDate}
            onClick={() => periodMutation.mutate()}
            className="min-h-10 rounded-md bg-accent px-4 text-sm font-semibold text-accent-foreground disabled:opacity-60"
          >
            {periodMutation.isPending ? "Saving…" : "Set Expiry Date"}
          </button>
        </div>
        {periodMutation.isError && (
          <p className="mt-2 text-xs text-chili">
            {axios.isAxiosError(periodMutation.error)
              ? String(periodMutation.error.response?.data?.detail ?? periodMutation.error.message)
              : "Failed to update expiry date."}
          </p>
        )}
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
