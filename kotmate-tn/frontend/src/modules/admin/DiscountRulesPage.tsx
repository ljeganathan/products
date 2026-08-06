import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import {
  type DiscountRule,
  type DiscountRuleCreatePayload,
  createDiscountRule,
  listDiscountRules,
  updateDiscountRule,
} from "@/modules/admin/discountRulesApi";
import { me } from "@/modules/auth/authApi";

const inputClass =
  "min-h-10 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";
const labelClass = "text-xs font-medium text-foreground/70";

const TYPE_LABELS: Record<string, string> = {
  flat_percent: "Flat %",
  item_level: "Item-level",
  coupon: "Coupon code",
};

function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && err.response?.data?.detail) {
    return String(err.response.data.detail);
  }
  return fallback;
}

interface DiscountRuleFormState {
  name: string;
  type: "flat_percent" | "item_level" | "coupon";
  value: string;
  coupon_code: string;
}

function DiscountRuleFormModal({
  editingRule,
  allowedTypes,
  onClose,
}: {
  editingRule: DiscountRule | null;
  allowedTypes: string[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<DiscountRuleFormState>(
    editingRule
      ? {
          name: editingRule.name,
          type: editingRule.type,
          value: editingRule.value != null ? String(editingRule.value) : "",
          coupon_code: editingRule.coupon_code ?? "",
        }
      : { name: "", type: (allowedTypes[0] as DiscountRuleFormState["type"]) ?? "flat_percent", value: "", coupon_code: "" },
  );
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      if (editingRule) {
        return updateDiscountRule(editingRule.id, {
          name: form.name,
          value: form.value ? Number(form.value) : null,
          coupon_code: form.type === "coupon" ? form.coupon_code : undefined,
        });
      }
      const payload: DiscountRuleCreatePayload = {
        name: form.name,
        type: form.type,
        value: form.value ? Number(form.value) : null,
        coupon_code: form.type === "coupon" ? form.coupon_code : null,
      };
      return createDiscountRule(payload);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["discount-rules"] });
      onClose();
    },
    onError: (err) => setError(apiErrorMessage(err, "Failed to save discount rule.")),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-lg bg-background p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-bold">{editingRule ? "Edit Discount Rule" : "Add Discount Rule"}</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Name</label>
            <input
              required
              placeholder="e.g. Festival Offer"
              className={inputClass}
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
          </div>

          {!editingRule && (
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Type</label>
              <select
                className={inputClass}
                value={form.type}
                onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as DiscountRuleFormState["type"] }))}
              >
                {allowedTypes.map((t) => (
                  <option key={t} value={t}>
                    {TYPE_LABELS[t] ?? t}
                  </option>
                ))}
              </select>
            </div>
          )}

          {form.type !== "item_level" && (
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Value (%)</label>
              <input
                type="number"
                min={0}
                max={100}
                className={inputClass}
                value={form.value}
                onChange={(e) => setForm((f) => ({ ...f, value: e.target.value }))}
              />
            </div>
          )}

          {form.type === "coupon" && (
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Coupon Code</label>
              <input
                required
                className={`${inputClass} uppercase`}
                value={form.coupon_code}
                onChange={(e) => setForm((f) => ({ ...f, coupon_code: e.target.value.toUpperCase() }))}
              />
            </div>
          )}

          {error && (
            <p role="alert" className="rounded-md bg-chili/10 px-3 py-2 text-sm text-chili">
              {error}
            </p>
          )}

          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-border px-4 py-2 text-sm font-semibold hover:bg-accent/10"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={mutation.isPending}
              className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-60"
            >
              {mutation.isPending ? "Saving…" : editingRule ? "Save Changes" : "Add Discount Rule"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function DiscountRulesPage() {
  const queryClient = useQueryClient();
  const { data: rules, isLoading, isError } = useQuery({
    queryKey: ["discount-rules"],
    queryFn: listDiscountRules,
  });
  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: me });
  const [formRule, setFormRule] = useState<DiscountRule | null | "new">(null);

  const allowedTypes =
    (meData?.features?.discount_types as unknown as string[] | undefined) ?? ["flat_percent"];

  const toggleActiveMutation = useMutation({
    mutationFn: (rule: DiscountRule) => updateDiscountRule(rule.id, { is_active: !rule.is_active }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["discount-rules"] }),
  });

  return (
    <div className="min-h-screen w-full bg-background p-6 text-foreground">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link to="/dashboard" className="text-xs text-foreground/50 hover:underline">
            ← Dashboard
          </Link>
          <h1 className="mt-1 text-xl font-bold">Discount Rules</h1>
          <p className="text-sm text-foreground/60">
            {allowedTypes.length === 1
              ? "Your plan (Lite) supports flat % discounts only."
              : `Your plan supports: ${allowedTypes.map((t) => TYPE_LABELS[t] ?? t).join(", ")}.`}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setFormRule("new")}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground"
        >
          + Add Discount Rule
        </button>
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {isError && <p className="text-sm text-chili">Failed to load discount rules.</p>}
      {rules && rules.length === 0 && !isLoading && (
        <p className="text-sm text-foreground/60">No discount rules yet.</p>
      )}

      {rules && rules.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-foreground/5 text-left text-xs uppercase tracking-wide text-foreground/60">
              <tr>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">Type</th>
                <th className="px-4 py-2.5">Value</th>
                <th className="px-4 py-2.5">Coupon Code</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id} className="border-t border-border">
                  <td className="px-4 py-2.5 font-bold">{rule.name}</td>
                  <td className="px-4 py-2.5 text-xs text-foreground/70">
                    {TYPE_LABELS[rule.type] ?? rule.type}
                  </td>
                  <td className="px-4 py-2.5">{rule.value != null ? `${rule.value}%` : "—"}</td>
                  <td className="px-4 py-2.5 font-mono text-xs">{rule.coupon_code ?? "—"}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        rule.is_active
                          ? "bg-accent/15 text-accent-foreground"
                          : "bg-foreground/10 text-foreground/50"
                      }`}
                    >
                      {rule.is_active ? "Active" : "Deactivated"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex gap-3 text-xs font-semibold">
                      <button
                        type="button"
                        onClick={() => setFormRule(rule)}
                        className="text-accent hover:underline"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleActiveMutation.mutate(rule)}
                        className={rule.is_active ? "text-chili hover:underline" : "text-accent hover:underline"}
                      >
                        {rule.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {formRule && (
        <DiscountRuleFormModal
          editingRule={formRule === "new" ? null : formRule}
          allowedTypes={allowedTypes}
          onClose={() => setFormRule(null)}
        />
      )}
    </div>
  );
}
