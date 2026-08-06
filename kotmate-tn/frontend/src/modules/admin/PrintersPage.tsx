import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { listLocations } from "@/modules/admin/locationsApi";
import {
  PRINTER_CONNECTION_TYPES,
  PRINTER_TARGETS,
  PRINTER_TYPES,
  type Printer,
  type PrinterCreatePayload,
  createPrinter,
  listPrinters,
  updatePrinter,
} from "@/modules/admin/printersApi";

const inputClass =
  "min-h-10 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";
const labelClass = "text-xs font-medium text-foreground/70";

function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && err.response?.data?.detail) {
    return String(err.response.data.detail);
  }
  return fallback;
}

interface PrinterFormState {
  location_id: string;
  name: string;
  target: string;
  printer_type: string;
  connection_type: string;
}

function PrinterFormModal({
  editingPrinter,
  locations,
  onClose,
}: {
  editingPrinter: Printer | null;
  locations: { id: string; name: string }[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<PrinterFormState>(
    editingPrinter
      ? {
          location_id: editingPrinter.location_id,
          name: editingPrinter.name,
          target: editingPrinter.target,
          printer_type: editingPrinter.printer_type,
          connection_type: editingPrinter.connection_type,
        }
      : {
          location_id: locations[0]?.id ?? "",
          name: "",
          target: PRINTER_TARGETS[0],
          printer_type: PRINTER_TYPES[0],
          connection_type: PRINTER_CONNECTION_TYPES[0],
        },
  );
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      const payload: PrinterCreatePayload = { ...form };
      return editingPrinter ? updatePrinter(editingPrinter.id, payload) : createPrinter(payload);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["printers"] });
      onClose();
    },
    onError: (err) => setError(apiErrorMessage(err, "Failed to save printer.")),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-lg bg-background p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-bold">{editingPrinter ? "Edit Printer" : "Add Printer"}</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Name</label>
            <input
              required
              placeholder="e.g. Kitchen Thermal Printer"
              className={inputClass}
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Target</label>
              <select
                required
                className={inputClass}
                value={form.target}
                onChange={(e) => setForm((f) => ({ ...f, target: e.target.value }))}
              >
                <option value="kot">KOT (kitchen)</option>
                <option value="bill">Bill (billing counter)</option>
              </select>
            </div>
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
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Printer Type</label>
              <select
                required
                className={inputClass}
                value={form.printer_type}
                onChange={(e) => setForm((f) => ({ ...f, printer_type: e.target.value }))}
              >
                <option value="thermal">Thermal (ESC/POS)</option>
                <option value="dotmatrix">Dot Matrix</option>
              </select>
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Connection</label>
              <select
                required
                className={inputClass}
                value={form.connection_type}
                onChange={(e) => setForm((f) => ({ ...f, connection_type: e.target.value }))}
              >
                <option value="network">Network</option>
                <option value="usb">USB</option>
                <option value="local_agent">Local Print Agent</option>
              </select>
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
              disabled={mutation.isPending || !form.location_id}
              className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-60"
            >
              {mutation.isPending ? "Saving…" : editingPrinter ? "Save Changes" : "Add Printer"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function PrintersPage() {
  const queryClient = useQueryClient();
  const { data: printers, isLoading, isError } = useQuery({ queryKey: ["printers"], queryFn: listPrinters });
  const { data: locations = [] } = useQuery({ queryKey: ["tenant-locations"], queryFn: listLocations });
  const [formPrinter, setFormPrinter] = useState<Printer | null | "new">(null);

  const locationNameById = new Map(locations.map((l) => [l.id, l.name]));

  const toggleActiveMutation = useMutation({
    mutationFn: (printer: Printer) => updatePrinter(printer.id, { is_active: !printer.is_active }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["printers"] }),
  });

  return (
    <div className="min-h-screen w-full bg-background p-6 text-foreground">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link to="/dashboard" className="text-xs text-foreground/50 hover:underline">
            ← Dashboard
          </Link>
          <h1 className="mt-1 text-xl font-bold">Printers</h1>
          <p className="text-sm text-foreground/60">
            Register a KOT (kitchen) and/or Bill printer per location — physical printing only
            fires on plans that include it (Pro/Pro Max).
          </p>
        </div>
        <button
          type="button"
          onClick={() => setFormPrinter("new")}
          disabled={locations.length === 0}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-60"
        >
          + Add Printer
        </button>
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {isError && <p className="text-sm text-chili">Failed to load printers.</p>}

      {printers && printers.length === 0 && !isLoading && (
        <p className="text-sm text-foreground/60">No printers registered yet.</p>
      )}

      {printers && printers.length > 0 && (
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-foreground/5 text-left text-xs uppercase tracking-wide text-foreground/60">
              <tr>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">Target</th>
                <th className="px-4 py-2.5">Type</th>
                <th className="px-4 py-2.5">Connection</th>
                <th className="px-4 py-2.5">Location</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody>
              {printers.map((printer) => (
                <tr key={printer.id} className="border-t border-border">
                  <td className="px-4 py-2.5 font-bold">{printer.name}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        printer.target === "kot" ? "bg-gold/15 text-gold" : "bg-accent/15 text-accent-foreground"
                      }`}
                    >
                      {printer.target === "kot" ? "KOT" : "Bill"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs capitalize text-foreground/70">{printer.printer_type}</td>
                  <td className="px-4 py-2.5 text-xs capitalize text-foreground/70">
                    {printer.connection_type.replace("_", " ")}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-foreground/70">
                    {locationNameById.get(printer.location_id) ?? "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        printer.is_active
                          ? "bg-accent/15 text-accent-foreground"
                          : "bg-foreground/10 text-foreground/50"
                      }`}
                    >
                      {printer.is_active ? "Active" : "Deactivated"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex gap-3 text-xs font-semibold">
                      <button
                        type="button"
                        onClick={() => setFormPrinter(printer)}
                        className="text-accent hover:underline"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleActiveMutation.mutate(printer)}
                        className={
                          printer.is_active ? "text-chili hover:underline" : "text-accent hover:underline"
                        }
                      >
                        {printer.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {formPrinter && (
        <PrinterFormModal
          editingPrinter={formPrinter === "new" ? null : formPrinter}
          locations={locations}
          onClose={() => setFormPrinter(null)}
        />
      )}
    </div>
  );
}
