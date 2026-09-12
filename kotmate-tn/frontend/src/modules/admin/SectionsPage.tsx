import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { type FormEvent, useState } from "react";

import { listLocations } from "@/modules/admin/locationsApi";
import { QrCodeImage } from "@/modules/admin/QrCodeImage";
import { generateSectionQrCode, getSectionQrCode } from "@/modules/admin/qrCodesApi";
import {
  type Section,
  type SectionCreatePayload,
  createSection,
  listSections,
  reorderSections,
  updateSection,
} from "@/modules/admin/sectionsApi";

const inputClass =
  "min-h-10 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";
const labelClass = "text-xs font-medium text-foreground/70";

function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && err.response?.data?.detail) {
    return String(err.response.data.detail);
  }
  return fallback;
}

interface SectionFormState {
  name_en: string;
  name_ta: string;
  is_seating: boolean;
}

function SectionFormModal({
  editingSection,
  onClose,
}: {
  editingSection: Section | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<SectionFormState>({
    name_en: editingSection?.name_en ?? "",
    name_ta: editingSection?.name_ta ?? "",
    is_seating: editingSection?.is_seating ?? true,
  });
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => {
      const payload: SectionCreatePayload = {
        name_en: form.name_en,
        name_ta: form.name_ta || undefined,
        is_seating: form.is_seating,
      };
      return editingSection ? updateSection(editingSection.id, payload) : createSection(payload);
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["sections"] });
      onClose();
    },
    onError: (err) => setError(apiErrorMessage(err, "Failed to save section.")),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-md rounded-lg bg-background p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-bold">{editingSection ? "Edit Section" : "Add Section"}</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Section Name (English)</label>
              <input
                required
                placeholder="e.g. AC"
                className={inputClass}
                value={form.name_en}
                onChange={(e) => setForm((f) => ({ ...f, name_en: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>பிரிவு பெயர் (தமிழ்)</label>
              <input
                className={inputClass}
                value={form.name_ta}
                onChange={(e) => setForm((f) => ({ ...f, name_ta: e.target.value }))}
              />
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.is_seating}
              onChange={(e) => setForm((f) => ({ ...f, is_seating: e.target.checked }))}
            />
            Is a physical seating area (requires a table number in POS)
          </label>
          <p className="-mt-2 text-xs text-foreground/50">
            Uncheck for Takeaway / Online Delivery-style sections, which skip table selection.
          </p>

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
              {mutation.isPending ? "Saving…" : editingSection ? "Save Changes" : "Create Section"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// Takeaway/Online Delivery QR (Phase 26) — the non-seating counterpart to Table
// Master's own QR modal, same copy-link behavior (including the http/LAN clipboard
// fallback). The one real difference: a section is tenant-wide, not per-location (a
// multi-location tenant's one "Takeaway" section is shared by every branch), so this
// modal needs its own location picker rather than inheriting one from a table row.
function SectionQrCodeModal({ section, onClose }: { section: Section; onClose: () => void }) {
  const queryClient = useQueryClient();
  const { data: locations = [] } = useQuery({ queryKey: ["tenant-locations"], queryFn: listLocations });
  const [locationId, setLocationId] = useState<string>("");
  const activeLocationId = locationId || locations[0]?.id || "";

  const { data: code, isLoading } = useQuery({
    queryKey: ["section-qr-code", section.id, activeLocationId],
    queryFn: () => getSectionQrCode(section.id, activeLocationId),
    enabled: !!activeLocationId,
  });
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState<string | null>(null);

  const generateMutation = useMutation({
    mutationFn: () => generateSectionQrCode(section.id, activeLocationId),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: ["section-qr-code", section.id, activeLocationId] }),
  });

  function scanUrl(qrToken: string): string {
    return `${window.location.origin}/order/${qrToken}`;
  }

  function legacyCopy(text: string): boolean {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    let ok = false;
    try {
      ok = document.execCommand("copy");
    } catch {
      ok = false;
    }
    document.body.removeChild(textarea);
    return ok;
  }

  async function handleCopy(qrToken: string) {
    const url = scanUrl(qrToken);
    setCopyError(null);
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(url);
      } else if (!legacyCopy(url)) {
        throw new Error("copy unsupported");
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopyError("Couldn't copy automatically — select and copy the link above manually.");
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-lg bg-background p-6 shadow-xl">
        <h2 className="mb-1 text-lg font-bold">QR Code — {section.name_en}</h2>
        <p className="mb-4 text-xs text-foreground/60">
          One QR code per branch — print it at the counter. Every scan starts its own independent
          order with its own pickup number; unlike a table, it's never shared between customers.
        </p>

        {locations.length > 1 && (
          <div className="mb-4 flex flex-col gap-1.5">
            <label className={labelClass}>Branch</label>
            <select
              className={inputClass}
              value={activeLocationId}
              onChange={(e) => setLocationId(e.target.value)}
            >
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name}
                </option>
              ))}
            </select>
          </div>
        )}

        {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}

        {!isLoading && !code && (
          <p className="mb-4 text-sm text-foreground/60">No QR code generated yet for this branch.</p>
        )}

        {code && (
          <div className="mb-4">
            <div className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2">
              <p className="min-w-0 select-all truncate font-mono text-xs">{scanUrl(code.qr_token)}</p>
              <button
                type="button"
                onClick={() => void handleCopy(code.qr_token)}
                className="shrink-0 rounded-md border border-border px-2.5 py-1 text-xs font-semibold hover:bg-accent/10"
              >
                {copied ? "Copied!" : "Copy link"}
              </button>
            </div>
            {copyError && <p className="mt-1 text-xs text-chili">{copyError}</p>}
            <QrCodeImage
              value={scanUrl(code.qr_token)}
              downloadName={`${section.name_en}-${
                locations.find((l) => l.id === activeLocationId)?.name ?? "qr"
              }`
                .toLowerCase()
                .replace(/[^a-z0-9]+/g, "-")
                .replace(/^-+|-+$/g, "")}
            />
          </div>
        )}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-border px-4 py-2 text-sm font-semibold hover:bg-accent/10"
          >
            Close
          </button>
          {!code && (
            <button
              type="button"
              onClick={() => generateMutation.mutate()}
              disabled={generateMutation.isPending || !activeLocationId}
              className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-60"
            >
              {generateMutation.isPending ? "Generating…" : "Generate QR Code"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export function SectionsPage() {
  const queryClient = useQueryClient();
  const { data: sections, isLoading, isError } = useQuery({
    queryKey: ["sections"],
    queryFn: listSections,
  });

  const [formSection, setFormSection] = useState<Section | null | "new">(null);
  const [qrSection, setQrSection] = useState<Section | null>(null);
  const [dragId, setDragId] = useState<string | null>(null);

  const reorderMutation = useMutation({
    mutationFn: (ordered: Section[]) =>
      reorderSections(ordered.map((s, index) => ({ id: s.id, display_order: index }))),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["sections"] }),
  });

  function handleDrop(targetId: string) {
    if (!sections || !dragId || dragId === targetId) return;
    const ordered = [...sections];
    const fromIndex = ordered.findIndex((s) => s.id === dragId);
    const toIndex = ordered.findIndex((s) => s.id === targetId);
    const [moved] = ordered.splice(fromIndex, 1);
    ordered.splice(toIndex, 0, moved);
    setDragId(null);
    reorderMutation.mutate(ordered);
  }

  return (
    <div className="min-h-screen w-full bg-background p-6 text-foreground">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="mt-1 text-xl font-bold">Seating Sections</h1>
          <p className="text-sm text-foreground/60">Drag rows to reorder; seeded by default at signup</p>
        </div>
        <button
          type="button"
          onClick={() => setFormSection("new")}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground"
        >
          + Add Section
        </button>
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {isError && <p className="text-sm text-chili">Failed to load sections.</p>}

      {sections && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-foreground/5 text-left text-xs uppercase tracking-wide text-foreground/60">
              <tr>
                <th className="w-8 px-4 py-2.5"></th>
                <th className="px-4 py-2.5">Name (English)</th>
                <th className="px-4 py-2.5">பெயர் (தமிழ்)</th>
                <th className="px-4 py-2.5">Type</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sections.map((section) => (
                <tr
                  key={section.id}
                  draggable
                  onDragStart={() => setDragId(section.id)}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={() => handleDrop(section.id)}
                  className={`cursor-move border-t border-border ${dragId === section.id ? "opacity-50" : ""}`}
                >
                  <td className="px-4 py-2.5 text-foreground/40">⠿</td>
                  <td className="px-4 py-2.5">{section.name_en}</td>
                  <td className="px-4 py-2.5">{section.name_ta || "—"}</td>
                  <td className="px-4 py-2.5 text-xs">
                    {section.is_seating ? (
                      <span className="rounded-full bg-gold/15 px-2 py-0.5 text-gold">Seating</span>
                    ) : (
                      <span className="rounded-full bg-foreground/10 px-2 py-0.5 text-foreground/60">
                        Non-seating
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        section.is_active
                          ? "bg-accent/15 text-accent-foreground"
                          : "bg-foreground/10 text-foreground/50"
                      }`}
                    >
                      {section.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        onClick={() => setFormSection(section)}
                        className="text-xs font-semibold text-accent hover:underline"
                      >
                        Edit
                      </button>
                      {!section.is_seating && (
                        <button
                          type="button"
                          onClick={() => setQrSection(section)}
                          className="text-xs font-semibold text-accent hover:underline"
                        >
                          QR Code
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {qrSection && <SectionQrCodeModal section={qrSection} onClose={() => setQrSection(null)} />}

      {formSection && (
        <SectionFormModal
          editingSection={formSection === "new" ? null : formSection}
          onClose={() => setFormSection(null)}
        />
      )}
    </div>
  );
}
