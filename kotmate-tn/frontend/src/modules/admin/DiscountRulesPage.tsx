import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { type FormEvent, useState } from "react";

import {
  type DiscountRule,
  type DiscountRuleCreatePayload,
  createDiscountRule,
  listDiscountRules,
  updateDiscountRule,
} from "@/modules/admin/discountRulesApi";
import { listItems } from "@/modules/admin/itemsApi";
import { me } from "@/modules/auth/authApi";

const inputClass =
  "min-h-10 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";
const labelClass = "text-xs font-medium text-foreground/70";

const TYPE_LABELS: Record<string, string> = {
  flat_percent: "Flat",
  item_level: "Item",
  coupon: "Coupon",
};

function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && err.response?.data?.detail) {
    return String(err.response.data.detail);
  }
  return fallback;
}

function generateCouponCode(): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  let code = "";
  for (let i = 0; i < 8; i++) code += chars[Math.floor(Math.random() * chars.length)];
  return code;
}

interface DiscountRuleFormState {
  name: string;
  type: "flat_percent" | "item_level" | "coupon";
  discount_mode: "percent" | "rupee";
  value: string;
  item_id: string;
  coupon_code: string;
  expires_at: string;
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
  const { data: items } = useQuery({ queryKey: ["items", "all"], queryFn: () => listItems() });
  const [form, setForm] = useState<DiscountRuleFormState>(
    editingRule
      ? {
          name: editingRule.name,
          type: editingRule.type,
          discount_mode: editingRule.discount_mode,
          value: editingRule.value != null ? String(editingRule.value) : "",
          item_id: editingRule.item_id ?? "",
          coupon_code: editingRule.coupon_code ?? "",
          expires_at: editingRule.expires_at ?? "",
        }
      : {
          name: "",
          type: (allowedTypes[0] as DiscountRuleFormState["type"]) ?? "flat_percent",
          discount_mode: "percent",
          value: "",
          item_id: "",
          coupon_code: "",
          expires_at: "",
        },
  );
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      const value = form.value ? Number(form.value) : null;
      const expires_at = form.expires_at || null;
      if (editingRule) {
        return updateDiscountRule(editingRule.id, {
          name: form.name,
          discount_mode: form.discount_mode,
          value,
          item_id: form.type === "item_level" ? form.item_id || null : undefined,
          coupon_code: form.type === "coupon" ? form.coupon_code : undefined,
          expires_at,
        });
      }
      const payload: DiscountRuleCreatePayload = {
        name: form.name,
        type: form.type,
        discount_mode: form.discount_mode,
        value,
        item_id: form.type === "item_level" ? form.item_id || null : null,
        coupon_code: form.type === "coupon" ? form.coupon_code : null,
        expires_at,
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

          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Type</label>
            <select
              disabled={!!editingRule}
              className={`${inputClass} disabled:opacity-60`}
              value={form.type}
              onChange={(e) => setForm((f) => ({ ...f, type: e.target.value as DiscountRuleFormState["type"] }))}
            >
              {(editingRule && !allowedTypes.includes(editingRule.type)
                ? [editingRule.type, ...allowedTypes]
                : allowedTypes
              ).map((t) => (
                <option key={t} value={t}>
                  {TYPE_LABELS[t] ?? t}
                </option>
              ))}
            </select>
            {editingRule && (
              <p className="text-[11px] text-foreground/50">Type can't be changed after creation.</p>
            )}
          </div>

          {form.type === "item_level" && (
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Item</label>
              <select
                required
                className={inputClass}
                value={form.item_id}
                onChange={(e) => setForm((f) => ({ ...f, item_id: e.target.value }))}
              >
                <option value="">Select an item…</option>
                {items?.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name_en}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Discount</label>
            <div className="flex gap-2">
              <div className="flex overflow-hidden rounded-md border border-border">
                {(["percent", "rupee"] as const).map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setForm((f) => ({ ...f, discount_mode: mode }))}
                    className={`min-h-10 px-3 text-sm font-semibold ${
                      form.discount_mode === mode
                        ? "bg-accent text-accent-foreground"
                        : "bg-background text-foreground/70 hover:bg-accent/10"
                    }`}
                  >
                    {mode === "percent" ? "%" : "₹"}
                  </button>
                ))}
              </div>
              <input
                type="number"
                min={0}
                max={form.discount_mode === "percent" ? 100 : undefined}
                placeholder={form.discount_mode === "percent" ? "e.g. 10" : "e.g. 50"}
                className={`${inputClass} flex-1`}
                value={form.value}
                onChange={(e) => setForm((f) => ({ ...f, value: e.target.value }))}
              />
            </div>
          </div>

          {form.type === "coupon" && (
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Coupon Code</label>
              <div className="flex gap-2">
                <input
                  required
                  className={`${inputClass} flex-1 uppercase`}
                  value={form.coupon_code}
                  onChange={(e) => setForm((f) => ({ ...f, coupon_code: e.target.value.toUpperCase() }))}
                />
                <button
                  type="button"
                  onClick={() => setForm((f) => ({ ...f, coupon_code: generateCouponCode() }))}
                  className="min-h-10 whitespace-nowrap rounded-md border border-accent bg-accent-soft px-3 text-sm font-semibold text-accent hover:bg-accent hover:text-accent-foreground"
                >
                  🎲 Generate
                </button>
              </div>
            </div>
          )}

          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Expires On (optional)</label>
            <input
              type="date"
              className={inputClass}
              value={form.expires_at}
              onChange={(e) => setForm((f) => ({ ...f, expires_at: e.target.value }))}
            />
          </div>

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

function formatValue(rule: DiscountRule): string {
  if (rule.value == null) return "—";
  return rule.discount_mode === "rupee" ? `₹${rule.value}` : `${rule.value}%`;
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
          <h1 className="mt-1 text-xl font-bold">Discount Rules</h1>
          <p className="text-sm text-foreground/60">
            {allowedTypes.length === 1
              ? "Your plan (Lite) supports Flat discounts only."
              : `Your plan supports: ${allowedTypes.map((t) => TYPE_LABELS[t] ?? t).join(", ")}.`}{" "}
            Active rules apply automatically at billing — Flat and Item rules need no cashier action; a
            Coupon needs the code entered at billing.
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
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-foreground/5 text-left text-xs uppercase tracking-wide text-foreground/60">
              <tr>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">Type</th>
                <th className="px-4 py-2.5">Value</th>
                <th className="px-4 py-2.5">Item</th>
                <th className="px-4 py-2.5">Coupon Code</th>
                <th className="px-4 py-2.5">Expires</th>
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
                  <td className="px-4 py-2.5">{formatValue(rule)}</td>
                  <td className="px-4 py-2.5 text-xs">{rule.item_name_en ?? "—"}</td>
                  <td className="px-4 py-2.5 font-mono text-xs">{rule.coupon_code ?? "—"}</td>
                  <td className="px-4 py-2.5 text-xs">{rule.expires_at ?? "Never"}</td>
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
