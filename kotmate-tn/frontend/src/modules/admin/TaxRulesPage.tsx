import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { type FormEvent, useState } from "react";

import { me } from "@/modules/auth/authApi";
import {
  type TaxRule,
  type TaxRuleCreatePayload,
  createTaxRule,
  listTaxRules,
  updateTaxRule,
} from "@/modules/admin/taxRulesApi";

const inputClass =
  "min-h-10 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";
const labelClass = "text-xs font-medium text-foreground/70";

function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && err.response?.data?.detail) {
    return String(err.response.data.detail);
  }
  return fallback;
}

interface TaxRuleFormState {
  name: string;
  cgst_rate: string;
  sgst_rate: string;
  is_default: boolean;
}

export function TaxRuleFormModal({
  editingRule,
  onClose,
}: {
  editingRule: TaxRule | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<TaxRuleFormState>(
    editingRule
      ? {
          name: editingRule.name,
          cgst_rate: String(editingRule.cgst_rate),
          sgst_rate: String(editingRule.sgst_rate),
          is_default: editingRule.is_default,
        }
      : { name: "", cgst_rate: "", sgst_rate: "", is_default: false },
  );
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      const payload: TaxRuleCreatePayload = {
        name: form.name,
        cgst_rate: Number(form.cgst_rate),
        sgst_rate: Number(form.sgst_rate),
        is_default: form.is_default,
      };
      return editingRule ? updateTaxRule(editingRule.id, payload) : createTaxRule(payload);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tax-rules"] });
      onClose();
    },
    onError: (err) => setError(apiErrorMessage(err, "Failed to save tax rule.")),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-lg bg-background p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-bold">{editingRule ? "Edit Tax Rule" : "Add Tax Rule"}</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Name</label>
            <input
              required
              placeholder="e.g. Standard GST"
              className={inputClass}
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>CGST %</label>
              <input
                required
                type="number"
                min={0}
                max={100}
                step="0.01"
                className={inputClass}
                value={form.cgst_rate}
                onChange={(e) => setForm((f) => ({ ...f, cgst_rate: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>SGST %</label>
              <input
                required
                type="number"
                min={0}
                max={100}
                step="0.01"
                className={inputClass}
                value={form.sgst_rate}
                onChange={(e) => setForm((f) => ({ ...f, sgst_rate: e.target.value }))}
              />
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_default}
              onChange={(e) => setForm((f) => ({ ...f, is_default: e.target.checked }))}
            />
            Default rate (applied when an item has no specific tax class)
          </label>

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
              {mutation.isPending ? "Saving…" : editingRule ? "Save Changes" : "Add Tax Rule"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function TaxRulesPage() {
  const queryClient = useQueryClient();
  const { data: rules, isLoading, isError } = useQuery({ queryKey: ["tax-rules"], queryFn: listTaxRules });
  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: me });
  const [formRule, setFormRule] = useState<TaxRule | null | "new">(null);

  const taxMode = (meData?.features?.tax_mode as unknown as string | undefined) ?? "single_rate";

  const toggleActiveMutation = useMutation({
    mutationFn: (rule: TaxRule) => updateTaxRule(rule.id, { is_active: !rule.is_active }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["tax-rules"] }),
  });

  return (
    <div className="min-h-screen w-full bg-background p-6 text-foreground">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="mt-1 text-xl font-bold">Tax Rules</h1>
          <p className="text-sm text-foreground/60">
            CGST and SGST are always tracked as two separate rates — never merged into one
            "GST" figure.{" "}
            {taxMode === "single_rate"
              ? "Your plan (Lite) applies a single flat rate to every bill."
              : "Assign a rate to individual items in Item Master to use more than one."}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setFormRule("new")}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground"
        >
          + Add Tax Rule
        </button>
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {isError && <p className="text-sm text-chili">Failed to load tax rules.</p>}
      {rules && rules.length === 0 && !isLoading && (
        <p className="text-sm text-foreground/60">No tax rules yet — bills will show ₹0 tax until one exists.</p>
      )}

      {rules && rules.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-foreground/5 text-left text-xs uppercase tracking-wide text-foreground/60">
              <tr>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">CGST</th>
                <th className="px-4 py-2.5">SGST</th>
                <th className="px-4 py-2.5">Default</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id} className="border-t border-border">
                  <td className="px-4 py-2.5 font-bold">{rule.name}</td>
                  <td className="px-4 py-2.5">{rule.cgst_rate}%</td>
                  <td className="px-4 py-2.5">{rule.sgst_rate}%</td>
                  <td className="px-4 py-2.5">
                    {rule.is_default && (
                      <span className="rounded-full bg-gold/15 px-2.5 py-0.5 text-xs font-semibold text-gold">
                        Default
                      </span>
                    )}
                  </td>
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
        <TaxRuleFormModal
          editingRule={formRule === "new" ? null : formRule}
          onClose={() => setFormRule(null)}
        />
      )}
    </div>
  );
}
