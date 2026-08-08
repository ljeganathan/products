import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";

import { formatINR } from "@/lib/utils";
import {
  createInvoice,
  listInvoices,
  listTenants,
  markInvoicePaid,
} from "@/modules/product-owner/platformApi";

const STATUS_FILTERS = ["all", "sent", "paid", "overdue"] as const;

function isOverdue(invoice: { status: string; due_date: string }): boolean {
  return invoice.status !== "paid" && invoice.due_date < new Date().toISOString().slice(0, 10);
}

const emptyForm = { tenant_id: "", amount: "", due_date: "", description: "" };

export function InvoicesPage() {
  const queryClient = useQueryClient();
  const [statusFilter, setStatusFilter] = useState<(typeof STATUS_FILTERS)[number]>("all");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);

  const { data: tenants = [] } = useQuery({ queryKey: ["tenants"], queryFn: listTenants });
  const { data: invoices = [], isLoading } = useQuery({
    queryKey: ["platform-invoices"],
    queryFn: () => listInvoices(),
  });

  const createMutation = useMutation({
    mutationFn: () =>
      createInvoice({
        tenant_id: form.tenant_id,
        amount: Number(form.amount),
        due_date: form.due_date,
        description: form.description || undefined,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["platform-invoices"] });
      void queryClient.invalidateQueries({ queryKey: ["platform-dashboard-alerts"] });
      setForm(emptyForm);
      setShowForm(false);
    },
  });

  const markPaidMutation = useMutation({
    mutationFn: (id: string) => markInvoicePaid(id),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["platform-invoices"] });
      void queryClient.invalidateQueries({ queryKey: ["platform-dashboard-alerts"] });
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate();
  }

  const visibleInvoices = invoices.filter((inv) => {
    if (statusFilter === "all") return true;
    if (statusFilter === "overdue") return isOverdue(inv);
    return inv.status === statusFilter;
  });

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-xl font-bold">Invoices</h1>
        <button
          type="button"
          onClick={() => setShowForm((v) => !v)}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground"
        >
          {showForm ? "Cancel" : "+ New Invoice"}
        </button>
      </div>

      {showForm && (
        <form
          onSubmit={handleSubmit}
          className="mb-6 flex flex-wrap items-end gap-3 rounded-lg border border-border p-4"
        >
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-foreground/70">Tenant</label>
            <select
              required
              className="min-h-10 rounded-md border border-border bg-background px-3 text-sm"
              value={form.tenant_id}
              onChange={(e) => setForm((f) => ({ ...f, tenant_id: e.target.value }))}
            >
              <option value="" disabled>
                Select tenant
              </option>
              {tenants.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.company_name}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-foreground/70">Amount (₹)</label>
            <input
              required
              type="number"
              min="1"
              step="0.01"
              className="min-h-10 w-32 rounded-md border border-border bg-background px-3 text-sm"
              value={form.amount}
              onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-foreground/70">Due Date</label>
            <input
              required
              type="date"
              className="min-h-10 rounded-md border border-border bg-background px-3 text-sm"
              value={form.due_date}
              onChange={(e) => setForm((f) => ({ ...f, due_date: e.target.value }))}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-medium text-foreground/70">Description</label>
            <input
              placeholder="e.g. Pro Max — Aug 2026"
              className="min-h-10 w-56 rounded-md border border-border bg-background px-3 text-sm"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="min-h-10 rounded-md bg-accent px-4 text-sm font-semibold text-accent-foreground disabled:opacity-60"
          >
            {createMutation.isPending ? "Creating…" : "Create"}
          </button>
        </form>
      )}

      <div className="mb-3 flex gap-2">
        {STATUS_FILTERS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setStatusFilter(s)}
            className={`rounded-full px-3 py-1 text-xs font-semibold capitalize ${
              statusFilter === s ? "bg-accent text-accent-foreground" : "border border-border text-foreground/70"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}

      {!isLoading && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-accent/5 text-left text-xs font-semibold uppercase tracking-wide text-foreground/60">
              <tr>
                <th className="px-3 py-2">Invoice #</th>
                <th className="px-3 py-2">Tenant</th>
                <th className="px-3 py-2">Amount</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Issued</th>
                <th className="px-3 py-2">Due</th>
                <th className="px-3 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {visibleInvoices.map((inv) => {
                const overdue = isOverdue(inv);
                return (
                  <tr key={inv.id} className="border-t border-border">
                    <td className="px-3 py-2 font-medium">{inv.invoice_number}</td>
                    <td className="px-3 py-2">{inv.tenant_company_name}</td>
                    <td className="px-3 py-2">{formatINR(inv.amount)}</td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                          inv.status === "paid"
                            ? "bg-accent/10 text-accent"
                            : overdue
                              ? "bg-chili/10 text-chili"
                              : "bg-gold/10 text-gold"
                        }`}
                      >
                        {inv.status === "paid" ? "paid" : overdue ? "overdue" : inv.status}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-foreground/70">{inv.issued_date}</td>
                    <td className="px-3 py-2 text-foreground/70">{inv.due_date}</td>
                    <td className="px-3 py-2 text-right">
                      {inv.status !== "paid" && (
                        <button
                          type="button"
                          disabled={markPaidMutation.isPending}
                          onClick={() => markPaidMutation.mutate(inv.id)}
                          className="text-xs font-semibold text-accent hover:underline disabled:opacity-60"
                        >
                          Mark Paid
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
              {visibleInvoices.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-6 text-center text-foreground/60">
                    No invoices.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
