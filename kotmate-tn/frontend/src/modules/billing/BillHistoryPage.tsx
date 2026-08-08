import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { formatINR } from "@/lib/utils";
import { listSections } from "@/modules/admin/sectionsApi";
import { listTables } from "@/modules/admin/tablesApi";
import { listUsers } from "@/modules/admin/usersApi";
import { listWaiters } from "@/modules/admin/waitersApi";
import { type BillSearchParams, listBills, reprintBill } from "@/modules/pos/billsApi";

const inputClass =
  "min-h-9 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";

export function BillHistoryPage() {
  const queryClient = useQueryClient();
  const { data: tables = [] } = useQuery({ queryKey: ["pos-tables"], queryFn: () => listTables() });
  const { data: waiters = [] } = useQuery({ queryKey: ["pos-waiters"], queryFn: () => listWaiters() });
  const { data: sections = [] } = useQuery({ queryKey: ["sections"], queryFn: listSections });
  const { data: users = [] } = useQuery({ queryKey: ["users"], queryFn: listUsers });
  const cashiers = users.filter((u) => u.role === "pos_user" || u.role === "tenant_admin");

  const [filters, setFilters] = useState<BillSearchParams>({});
  const [reprintingId, setReprintingId] = useState<string | null>(null);

  const { data: bills, isLoading, isError } = useQuery({
    queryKey: ["bills", filters],
    queryFn: () => listBills(filters),
  });

  const reprintMutation = useMutation({
    mutationFn: (id: string) => reprintBill(id),
    onMutate: (id) => setReprintingId(id),
    onSettled: () => setReprintingId(null),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["bills"] }),
  });

  const tableNumberById = new Map(tables.map((t) => [t.id, t.table_number]));
  const waiterNameById = new Map(waiters.map((w) => [w.id, w.name]));

  return (
    <div className="min-h-screen w-full bg-background p-6 text-foreground">
      <div className="mb-6">
        <h1 className="mt-1 text-xl font-bold">Bill History</h1>
        <p className="text-sm text-foreground/60">
          Search old bills by number, date, seating section, waiter, or cashier — and reprint any of them.
        </p>
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 rounded-lg border border-border bg-surface p-4 sm:grid-cols-3 lg:grid-cols-6">
        <input
          placeholder="Bill number"
          className={inputClass}
          value={filters.bill_number ?? ""}
          onChange={(e) => setFilters((f) => ({ ...f, bill_number: e.target.value || undefined }))}
        />
        <input
          type="date"
          className={inputClass}
          value={filters.date_from ?? ""}
          onChange={(e) => setFilters((f) => ({ ...f, date_from: e.target.value || undefined }))}
        />
        <input
          type="date"
          className={inputClass}
          value={filters.date_to ?? ""}
          onChange={(e) => setFilters((f) => ({ ...f, date_to: e.target.value || undefined }))}
        />
        <select
          className={inputClass}
          value={filters.section_id ?? ""}
          onChange={(e) => setFilters((f) => ({ ...f, section_id: e.target.value || undefined }))}
        >
          <option value="">All sections</option>
          {sections.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name_en}
            </option>
          ))}
        </select>
        <select
          className={inputClass}
          value={filters.waiter_id ?? ""}
          onChange={(e) => setFilters((f) => ({ ...f, waiter_id: e.target.value || undefined }))}
        >
          <option value="">All waiters</option>
          {waiters.map((w) => (
            <option key={w.id} value={w.id}>
              {w.name}
            </option>
          ))}
        </select>
        <select
          className={inputClass}
          value={filters.pos_user_id ?? ""}
          onChange={(e) => setFilters((f) => ({ ...f, pos_user_id: e.target.value || undefined }))}
        >
          <option value="">All cashiers</option>
          {cashiers.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name} ({c.user_id})
            </option>
          ))}
        </select>
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {isError && <p className="text-sm text-chili">Failed to load bills.</p>}
      {bills && bills.length === 0 && !isLoading && (
        <p className="text-sm text-foreground/60">No bills match these filters.</p>
      )}

      {bills && bills.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-foreground/5 text-left text-xs uppercase tracking-wide text-foreground/60">
              <tr>
                <th className="px-4 py-2.5">Bill #</th>
                <th className="px-4 py-2.5">Date</th>
                <th className="px-4 py-2.5">Table</th>
                <th className="px-4 py-2.5">Waiter</th>
                <th className="px-4 py-2.5">Cashier</th>
                <th className="px-4 py-2.5 text-right">Grand Total</th>
                <th className="px-4 py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody>
              {bills.map((bill) => (
                <tr key={bill.id} className="border-t border-border">
                  <td className="px-4 py-2.5 font-bold">{bill.bill_number}</td>
                  <td className="px-4 py-2.5 text-xs text-foreground/70">
                    {new Date(bill.created_at).toLocaleString("en-IN")}
                  </td>
                  <td className="px-4 py-2.5 text-xs">
                    {bill.table_number ?? tableNumberById.get(bill.table_id ?? "") ?? bill.section_name_en}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-foreground/70">
                    {bill.waiter_name ?? waiterNameById.get(bill.waiter_id ?? "") ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-foreground/70">{bill.pos_user_login_id}</td>
                  <td className="px-4 py-2.5 text-right font-bold tabular-nums">
                    {formatINR(bill.grand_total)}
                  </td>
                  <td className="px-4 py-2.5">
                    <button
                      type="button"
                      onClick={() => reprintMutation.mutate(bill.id)}
                      disabled={reprintingId === bill.id}
                      className="text-xs font-semibold text-accent hover:underline disabled:opacity-50"
                    >
                      {reprintingId === bill.id ? "Printing…" : "🖨 Reprint"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
