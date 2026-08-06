import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { listLocations } from "@/modules/admin/locationsApi";
import { listUsers } from "@/modules/admin/usersApi";
import {
  type Waiter,
  type WaiterCreatePayload,
  createWaiter,
  listWaiters,
  updateWaiter,
} from "@/modules/admin/waitersApi";

const inputClass =
  "min-h-10 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";
const labelClass = "text-xs font-medium text-foreground/70";

function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && err.response?.data?.detail) {
    return String(err.response.data.detail);
  }
  return fallback;
}

interface WaiterFormState {
  location_id: string;
  waiter_number: string;
  name: string;
  phone: string;
  incentive_rate: string;
  user_id: string;
}

function WaiterFormModal({
  editingWaiter,
  locations,
  linkableUsers,
  onClose,
}: {
  editingWaiter: Waiter | null;
  locations: { id: string; name: string }[];
  linkableUsers: { id: string; label: string }[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<WaiterFormState>(
    editingWaiter
      ? {
          location_id: editingWaiter.location_id,
          waiter_number: editingWaiter.waiter_number,
          name: editingWaiter.name,
          phone: editingWaiter.phone ?? "",
          incentive_rate: editingWaiter.incentive_rate?.toString() ?? "",
          user_id: editingWaiter.user_id ?? "",
        }
      : {
          location_id: locations[0]?.id ?? "",
          waiter_number: "",
          name: "",
          phone: "",
          incentive_rate: "",
          user_id: "",
        },
  );
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      const payload: WaiterCreatePayload = {
        location_id: form.location_id,
        waiter_number: form.waiter_number,
        name: form.name,
        phone: form.phone || undefined,
        incentive_rate: form.incentive_rate ? Number(form.incentive_rate) : null,
        user_id: form.user_id || null,
      };
      return editingWaiter ? updateWaiter(editingWaiter.id, payload) : createWaiter(payload);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["waiters"] });
      onClose();
    },
    onError: (err) => setError(apiErrorMessage(err, "Failed to save waiter.")),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-lg bg-background p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-bold">{editingWaiter ? "Edit Waiter" : "Add Waiter"}</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Waiter Number</label>
              <input
                required
                placeholder="e.g. W1"
                className={inputClass}
                value={form.waiter_number}
                onChange={(e) => setForm((f) => ({ ...f, waiter_number: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Name</label>
              <input
                required
                className={inputClass}
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Location</label>
              <select
                required
                className={inputClass}
                value={form.location_id}
                onChange={(e) => setForm((f) => ({ ...f, location_id: e.target.value }))}
              >
                {locations.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Phone</label>
              <input
                className={inputClass}
                value={form.phone}
                onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Incentive Rate (% of net sale value)</label>
              <input
                type="number"
                min={0}
                max={100}
                step="0.1"
                className={inputClass}
                value={form.incentive_rate}
                onChange={(e) => setForm((f) => ({ ...f, incentive_rate: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Login Account (optional)</label>
              <select
                className={inputClass}
                value={form.user_id}
                onChange={(e) => setForm((f) => ({ ...f, user_id: e.target.value }))}
              >
                <option value="">Not linked</option>
                {linkableUsers.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.label}
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-foreground/50">
                Links this waiter to a Waiter-role login so POS auto-attributes their orders.
              </p>
            </div>
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
              {mutation.isPending ? "Saving…" : editingWaiter ? "Save Changes" : "Create Waiter"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function WaitersPage() {
  const queryClient = useQueryClient();
  const { data: waiters, isLoading, isError } = useQuery({ queryKey: ["waiters"], queryFn: listWaiters });
  const { data: locations = [] } = useQuery({ queryKey: ["tenant-locations"], queryFn: listLocations });
  const { data: users = [] } = useQuery({ queryKey: ["tenant-users"], queryFn: listUsers });
  const [formWaiter, setFormWaiter] = useState<Waiter | null | "new">(null);

  const locationNameById = new Map(locations.map((l) => [l.id, l.name]));
  const linkedUserIds = new Set(
    (waiters ?? [])
      .filter((w) => w.id !== (formWaiter !== "new" ? formWaiter?.id : undefined))
      .map((w) => w.user_id)
      .filter((id): id is string => id != null),
  );
  const linkableUsers = users
    .filter((u) => u.role === "waiter" && !linkedUserIds.has(u.id))
    .map((u) => ({ id: u.id, label: `${u.name} (${u.user_id})` }));

  const toggleActiveMutation = useMutation({
    mutationFn: (waiter: Waiter) => updateWaiter(waiter.id, { is_active: !waiter.is_active }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["waiters"] }),
  });

  return (
    <div className="min-h-screen w-full bg-background p-6 text-foreground">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link to="/dashboard" className="text-xs text-foreground/50 hover:underline">
            ← Dashboard
          </Link>
          <h1 className="mt-1 text-xl font-bold">Waiter Master</h1>
          <p className="text-sm text-foreground/60">Incentive rate applies to net sale value per bill</p>
        </div>
        <button
          type="button"
          onClick={() => setFormWaiter("new")}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground"
        >
          + Add Waiter
        </button>
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {isError && <p className="text-sm text-chili">Failed to load waiters.</p>}

      {waiters && (
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-foreground/5 text-left text-xs uppercase tracking-wide text-foreground/60">
              <tr>
                <th className="px-4 py-2.5">No.</th>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">Location</th>
                <th className="px-4 py-2.5">Phone</th>
                <th className="px-4 py-2.5">Incentive</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody>
              {waiters.map((waiter) => (
                <tr key={waiter.id} className="border-t border-border">
                  <td className="px-4 py-2.5 font-mono text-xs">{waiter.waiter_number}</td>
                  <td className="px-4 py-2.5">{waiter.name}</td>
                  <td className="px-4 py-2.5 text-xs text-foreground/70">
                    {locationNameById.get(waiter.location_id) ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-foreground/70">{waiter.phone || "—"}</td>
                  <td className="px-4 py-2.5 text-xs">
                    {waiter.incentive_rate != null ? `${waiter.incentive_rate}%` : "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        waiter.is_active
                          ? "bg-accent/15 text-accent-foreground"
                          : "bg-foreground/10 text-foreground/50"
                      }`}
                    >
                      {waiter.is_active ? "Active" : "Deactivated"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex gap-3 text-xs font-semibold">
                      <button
                        type="button"
                        onClick={() => setFormWaiter(waiter)}
                        className="text-accent hover:underline"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleActiveMutation.mutate(waiter)}
                        className={waiter.is_active ? "text-chili hover:underline" : "text-accent hover:underline"}
                      >
                        {waiter.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {formWaiter && (
        <WaiterFormModal
          editingWaiter={formWaiter === "new" ? null : formWaiter}
          locations={locations}
          linkableUsers={linkableUsers}
          onClose={() => setFormWaiter(null)}
        />
      )}
    </div>
  );
}
