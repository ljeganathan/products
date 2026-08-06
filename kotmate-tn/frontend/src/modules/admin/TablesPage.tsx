import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { type FormEvent, useState } from "react";
import { Link } from "react-router-dom";

import { listLocations } from "@/modules/admin/locationsApi";
import { listSections, type Section } from "@/modules/admin/sectionsApi";
import {
  type Table,
  type TableCreatePayload,
  createTable,
  listTables,
  updateTable,
} from "@/modules/admin/tablesApi";

const inputClass =
  "min-h-10 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";
const labelClass = "text-xs font-medium text-foreground/70";

const TAG_COLORS = [
  "bg-gold/15 text-gold",
  "bg-chili/15 text-chili",
  "bg-accent/15 text-accent-foreground",
];

function sectionTagColor(sectionId: string, sections: Section[]): string {
  const index = sections.findIndex((s) => s.id === sectionId);
  return TAG_COLORS[index % TAG_COLORS.length];
}

function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && err.response?.data?.detail) {
    return String(err.response.data.detail);
  }
  return fallback;
}

interface TableFormState {
  location_id: string;
  section_id: string;
  table_number: string;
  seating_capacity: string;
}

function TableFormModal({
  editingTable,
  locations,
  seatingSections,
  onClose,
}: {
  editingTable: Table | null;
  locations: { id: string; name: string }[];
  seatingSections: Section[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<TableFormState>(
    editingTable
      ? {
          location_id: editingTable.location_id,
          section_id: editingTable.section_id,
          table_number: editingTable.table_number,
          seating_capacity: editingTable.seating_capacity?.toString() ?? "",
        }
      : {
          location_id: locations[0]?.id ?? "",
          section_id: seatingSections[0]?.id ?? "",
          table_number: "",
          seating_capacity: "",
        },
  );
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      const payload: TableCreatePayload = {
        location_id: form.location_id,
        section_id: form.section_id,
        table_number: form.table_number,
        seating_capacity: form.seating_capacity ? Number(form.seating_capacity) : null,
      };
      return editingTable ? updateTable(editingTable.id, payload) : createTable(payload);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tables"] });
      onClose();
    },
    onError: (err) => setError(apiErrorMessage(err, "Failed to save table.")),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-lg bg-background p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-bold">{editingTable ? "Edit Table" : "Add Table"}</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Table Number</label>
              <input
                required
                placeholder="e.g. T5"
                className={inputClass}
                value={form.table_number}
                onChange={(e) => setForm((f) => ({ ...f, table_number: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Seating Capacity</label>
              <input
                type="number"
                min={1}
                className={inputClass}
                value={form.seating_capacity}
                onChange={(e) => setForm((f) => ({ ...f, seating_capacity: e.target.value }))}
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
              <label className={labelClass}>Section</label>
              <select
                required
                className={inputClass}
                value={form.section_id}
                onChange={(e) => setForm((f) => ({ ...f, section_id: e.target.value }))}
              >
                {seatingSections.length === 0 && <option value="">No seating sections available</option>}
                {seatingSections.map((section) => (
                  <option key={section.id} value={section.id}>
                    {section.name_en}
                  </option>
                ))}
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
              disabled={mutation.isPending || !form.section_id}
              className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-60"
            >
              {mutation.isPending ? "Saving…" : editingTable ? "Save Changes" : "Create Table"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export function TablesPage() {
  const queryClient = useQueryClient();
  const { data: tables, isLoading, isError } = useQuery({ queryKey: ["tables"], queryFn: listTables });
  const { data: locations = [] } = useQuery({ queryKey: ["tenant-locations"], queryFn: listLocations });
  const { data: sections = [] } = useQuery({ queryKey: ["sections"], queryFn: listSections });
  const [formTable, setFormTable] = useState<Table | null | "new">(null);

  const seatingSections = sections.filter((s) => s.is_seating && s.is_active);
  const locationNameById = new Map(locations.map((l) => [l.id, l.name]));
  const sectionById = new Map(sections.map((s) => [s.id, s]));

  const toggleActiveMutation = useMutation({
    mutationFn: (table: Table) => updateTable(table.id, { is_active: !table.is_active }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["tables"] }),
  });

  return (
    <div className="min-h-screen w-full bg-background p-6 text-foreground">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <Link to="/dashboard" className="text-xs text-foreground/50 hover:underline">
            ← Dashboard
          </Link>
          <h1 className="mt-1 text-xl font-bold">Table Master</h1>
          <p className="text-sm text-foreground/60">Every table belongs to a physical seating section</p>
        </div>
        <button
          type="button"
          onClick={() => setFormTable("new")}
          disabled={seatingSections.length === 0}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-60"
        >
          + Add Table
        </button>
      </div>

      {seatingSections.length === 0 && !isLoading && (
        <p className="mb-4 rounded-md bg-gold/10 px-3 py-2 text-sm text-gold">
          No active seating sections yet — add one in Seating Sections before creating tables.
        </p>
      )}

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {isError && <p className="text-sm text-chili">Failed to load tables.</p>}

      {tables && (
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-foreground/5 text-left text-xs uppercase tracking-wide text-foreground/60">
              <tr>
                <th className="px-4 py-2.5">Table</th>
                <th className="px-4 py-2.5">Section</th>
                <th className="px-4 py-2.5">Location</th>
                <th className="px-4 py-2.5">Capacity</th>
                <th className="px-4 py-2.5">Floor Status</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody>
              {tables.map((table) => (
                <tr key={table.id} className="border-t border-border">
                  <td className="px-4 py-2.5 font-bold">{table.table_number}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${sectionTagColor(table.section_id, sections)}`}
                    >
                      {sectionById.get(table.section_id)?.name_en ?? "—"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-foreground/70">
                    {locationNameById.get(table.location_id) ?? "—"}
                  </td>
                  <td className="px-4 py-2.5 text-xs">{table.seating_capacity ?? "—"}</td>
                  <td className="px-4 py-2.5 text-xs capitalize text-foreground/70">{table.status}</td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        table.is_active
                          ? "bg-accent/15 text-accent-foreground"
                          : "bg-foreground/10 text-foreground/50"
                      }`}
                    >
                      {table.is_active ? "Active" : "Deactivated"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex gap-3 text-xs font-semibold">
                      <button
                        type="button"
                        onClick={() => setFormTable(table)}
                        className="text-accent hover:underline"
                      >
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => toggleActiveMutation.mutate(table)}
                        className={table.is_active ? "text-chili hover:underline" : "text-accent hover:underline"}
                      >
                        {table.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {formTable && (
        <TableFormModal
          editingTable={formTable === "new" ? null : formTable}
          locations={locations}
          seatingSections={seatingSections}
          onClose={() => setFormTable(null)}
        />
      )}
    </div>
  );
}
