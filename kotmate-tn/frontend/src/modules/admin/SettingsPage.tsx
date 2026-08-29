import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Switch } from "@/components/ui/Switch";
import { resolveAssetUrl } from "@/lib/api";
import { INDIAN_STATES, gstinStateWarning } from "@/lib/constants";
import { me, type MeResponse } from "@/modules/auth/authApi";
import {
  type HotelMaster,
  type HotelMasterUpdatePayload,
  getHotelMaster,
  removeHotelMasterLogo,
  saveHotelMaster,
  uploadHotelMasterLogo,
} from "@/modules/admin/hotelMasterApi";
import {
  type LocationCreatePayload,
  type LocationDetail,
  createLocation,
  listManagedLocations,
  updateLocation,
} from "@/modules/admin/locationsApi";
import { updateCategoryDisplaySetting } from "@/modules/admin/categoryDisplaySettingsApi";
import { updateDefaultPaymentMethod } from "@/modules/admin/paymentPreferencesApi";
import { updatePosLayoutSetting, updateWaiterMandatorySetting } from "@/modules/admin/posLayoutSettingsApi";
import { PrinterFormModal } from "@/modules/admin/PrintersPage";
import { type Printer, listPrinters } from "@/modules/admin/printersApi";
import {
  updateReportPrintingSetting,
  updateReportTamilNamesSetting,
} from "@/modules/admin/reportPrintingSettingsApi";
import { updateStockManagementSetting } from "@/modules/admin/stockSettingsApi";
import { type TaxRule, listTaxRules } from "@/modules/admin/taxRulesApi";
import { TaxRuleFormModal } from "@/modules/admin/TaxRulesPage";

const inputClass =
  "min-h-10 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";
const labelClass = "text-xs font-medium text-foreground/70";

const TABS = ["General", "Locations", "Printers", "Tax", "Preferences"] as const;
type Tab = (typeof TABS)[number];

function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && err.response?.data?.detail) {
    return String(err.response.data.detail);
  }
  return fallback;
}

export function SettingsPage() {
  const [tab, setTab] = useState<Tab>("General");
  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: me });
  const { data: locations = [], isLoading: locationsLoading } = useQuery({
    queryKey: ["managed-locations"],
    queryFn: listManagedLocations,
  });
  const activeLocations = locations.filter((l) => l.is_active);
  const [selectedLocationId, setSelectedLocationId] = useState<string>("");

  useEffect(() => {
    if (!selectedLocationId && activeLocations.length > 0) {
      setSelectedLocationId(activeLocations[0].id);
    }
  }, [activeLocations, selectedLocationId]);

  return (
    <div className="min-h-screen w-full bg-background p-6 text-foreground">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="mt-1 text-xl font-bold">Settings</h1>
          <p className="text-sm text-foreground/60">
            Company Master, per-location Hotel Master, printers, tax, and categories.
          </p>
        </div>
        {activeLocations.length > 1 &&
          (tab === "General" || tab === "Printers" || tab === "Tax" || tab === "Preferences") && (
          <div className="flex flex-col gap-1">
            <label className={labelClass}>Location</label>
            <select
              className={inputClass}
              value={selectedLocationId}
              onChange={(e) => setSelectedLocationId(e.target.value)}
            >
              {activeLocations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      <div className="mb-6 flex gap-1 border-b border-border">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`border-b-2 px-4 py-2 text-sm font-semibold ${
              tab === t
                ? "border-accent text-accent"
                : "border-transparent text-foreground/60 hover:text-foreground"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {locationsLoading && <p className="text-sm text-foreground/60">Loading…</p>}

      {tab === "General" &&
        (selectedLocationId ? (
          <GeneralTab locationId={selectedLocationId} />
        ) : (
          !locationsLoading && <p className="text-sm text-foreground/60">Add a location first.</p>
        ))}
      {tab === "Locations" && <LocationsTab locations={locations} />}
      {tab === "Printers" && <PrintersTab locations={activeLocations} />}
      {tab === "Tax" && <TaxTab />}
      {tab === "Preferences" && (
        <PreferencesTab meData={meData} locationId={selectedLocationId} locationsLoading={locationsLoading} />
      )}
    </div>
  );
}

function PreferencesTab({
  meData,
  locationId,
  locationsLoading,
}: {
  meData: MeResponse | undefined;
  locationId: string;
  locationsLoading: boolean;
}) {
  const queryClient = useQueryClient();
  const invalidateMe = () => void queryClient.invalidateQueries({ queryKey: ["me"] });

  // Pro/Pro Max-only surfaces — the underlying stock badges/decrement stay on for Lite
  // too, but each toggle here is a new admin-controlled surface layered on top, so it's
  // gated on the plan feature specifically, not the effective flag.
  const stockManagementOnPlan = meData?.features?.stock_management === true;
  const reportPrintingOnPlan = meData?.features?.report_printing === true;

  const categoryDisplayMutation = useMutation({
    mutationFn: (next: boolean) => updateCategoryDisplaySetting(next),
    onSuccess: invalidateMe,
  });
  const stockManagementMutation = useMutation({
    mutationFn: (next: boolean) => updateStockManagementSetting(next),
    onSuccess: invalidateMe,
  });
  const reportPrintingMutation = useMutation({
    mutationFn: (next: boolean) => updateReportPrintingSetting(next),
    onSuccess: invalidateMe,
  });
  const reportTamilNamesMutation = useMutation({
    mutationFn: (next: boolean) => updateReportTamilNamesSetting(next),
    onSuccess: invalidateMe,
  });
  const paymentMethodMutation = useMutation({
    mutationFn: (method: "upi" | "cash" | "card") => updateDefaultPaymentMethod(method),
    onSuccess: invalidateMe,
  });
  const posLayoutMutation = useMutation({
    mutationFn: (layout: "default" | "guided") => updatePosLayoutSetting(layout),
    onSuccess: invalidateMe,
  });
  const waiterMandatoryMutation = useMutation({
    mutationFn: (next: boolean) => updateWaiterMandatorySetting(next),
    onSuccess: invalidateMe,
  });

  const posLayout = meData?.pos_layout ?? "default";

  return (
    <div className="flex max-w-xl flex-col gap-4">
      <div className="rounded-lg border border-border bg-surface p-4">
        <label className="mb-1.5 block text-sm font-medium text-foreground" htmlFor="pos-layout-select">
          POS Layout
        </label>
        <select
          id="pos-layout-select"
          value={posLayout}
          disabled={posLayoutMutation.isPending}
          onChange={(e) => posLayoutMutation.mutate(e.target.value as "default" | "guided")}
          className="rounded-md border border-border bg-background px-3 py-2 text-sm font-semibold disabled:opacity-60"
        >
          <option value="default">Default</option>
          <option value="guided">Guided POS</option>
        </select>
        <p className="mt-2 text-xs text-foreground/50">
          Which POS screen your staff land on at /pos. Guided POS is desktop/tablet only —
          on a phone-width screen every tenant always gets the Default layout regardless of
          this setting.
        </p>
      </div>

      <div className="rounded-lg border border-border bg-surface p-4">
        <Switch
          checked={meData?.waiter_mandatory_enabled !== false}
          disabled={waiterMandatoryMutation.isPending}
          onChange={(next) => waiterMandatoryMutation.mutate(next)}
          label="Require waiter selection"
          description="When off, billing a dine-in order no longer requires a waiter to be assigned first, on either POS layout — the bill just shows Unassigned. Takeaway/Online Delivery orders never require a waiter regardless of this setting."
        />
      </div>

      <div className="rounded-lg border border-border bg-surface p-4">
        <Switch
          checked={meData?.show_tamil_categories !== false}
          disabled={categoryDisplayMutation.isPending}
          onChange={(next) => categoryDisplayMutation.mutate(next)}
          label="Show Tamil names on the POS category list"
          description="Applies only to the category rail/strip. Item buttons on the main grid always show English and Tamil together, and this doesn't affect printed KOT tickets or bills."
        />
      </div>

      <div className="rounded-lg border border-border bg-surface p-4">
        {locationsLoading ? (
          <p className="text-sm text-foreground/60">Loading…</p>
        ) : locationId ? (
          <TamilPrintToggle locationId={locationId} />
        ) : (
          <p className="text-sm text-foreground/60">Add a location first.</p>
        )}
      </div>

      <div className="rounded-lg border border-border bg-surface p-4">
        <p className="mb-2 text-sm font-medium text-foreground">Default payment method</p>
        <div className="flex gap-1.5">
          {(["upi", "cash", "card"] as const).map((method) => (
            <button
              key={method}
              type="button"
              disabled={paymentMethodMutation.isPending}
              onClick={() => paymentMethodMutation.mutate(method)}
              className={`rounded-md border px-3.5 py-2 text-xs font-semibold uppercase disabled:opacity-60 ${
                (meData?.default_payment_method ?? "cash") === method
                  ? "border-accent bg-accent-soft text-accent"
                  : "border-border text-foreground/70 hover:border-foreground/30"
              }`}
            >
              {method}
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-foreground/50">
          Pre-selected on the POS billing screen — cashiers can still change it per bill.
        </p>
      </div>

      {stockManagementOnPlan && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <Switch
            checked={meData?.stock_tracking_enabled === true}
            disabled={stockManagementMutation.isPending}
            onChange={(next) => stockManagementMutation.mutate(next)}
            label="Enable stock-quantity tracking"
            description="Turns on quantity badges on the POS/KOT screens and the Stock Management tab on the KOT screen. Turning this off never clears any item's tracked quantity or history."
          />
        </div>
      )}

      {reportPrintingOnPlan && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <Switch
            checked={meData?.report_printing_enabled === true}
            disabled={reportPrintingMutation.isPending}
            onChange={(next) => reportPrintingMutation.mutate(next)}
            label="Enable report printing"
            description="Lets Reports be sent to a Reports-target printer (Settings > Printers) directly from the Reports page. Pro Max only."
          />
        </div>
      )}

      {reportPrintingOnPlan && (
        <div className="rounded-lg border border-border bg-surface p-4">
          <Switch
            checked={meData?.report_tamil_names_enabled === true}
            disabled={reportTamilNamesMutation.isPending}
            onChange={(next) => reportTamilNamesMutation.mutate(next)}
            label="Print item/category names in Tamil"
            description="Applies to Item Wise Sales and Category Wise Sales report prints only. Rasterized on a thermal Reports printer; a dot-matrix Reports printer always prints English (no image support)."
          />
        </div>
      )}
    </div>
  );
}

function TamilPrintToggle({ locationId }: { locationId: string }) {
  const queryClient = useQueryClient();
  const { data: hotel, isLoading } = useQuery({
    queryKey: ["hotel-master", locationId],
    queryFn: () => getHotelMaster(locationId),
  });
  const mutation = useMutation({
    mutationFn: (next: boolean) =>
      saveHotelMaster({
        location_id: locationId,
        name: hotel?.name ?? "",
        door_no: hotel?.door_no,
        street: hotel?.street,
        city: hotel?.city,
        district: hotel?.district,
        state: hotel?.state,
        pincode: hotel?.pincode,
        phone: hotel?.phone,
        gstin: hotel?.gstin,
        upi_id: hotel?.upi_id,
        show_tamil_names: next,
        receipt_footer_message: hotel?.receipt_footer_message,
      }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["hotel-master", locationId] }),
  });

  if (isLoading || !hotel) return <p className="text-sm text-foreground/60">Loading…</p>;

  return (
    <Switch
      checked={hotel.show_tamil_names}
      disabled={mutation.isPending}
      onChange={(next) => mutation.mutate(next)}
      label="Show Tamil item names on printed KOT tickets and bills"
      description="Set per location — this only affects the printed copy. The POS staff screen always shows English and Tamil together, regardless of this setting."
    />
  );
}

function PrintersTab({ locations }: { locations: LocationDetail[] }) {
  const { data: printers = [], isLoading } = useQuery({ queryKey: ["printers"], queryFn: listPrinters });
  const [showForm, setShowForm] = useState(false);

  return (
    <div className="max-w-lg rounded-lg border border-border bg-surface p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="mb-1 text-base font-bold">Printers</h2>
          <p className="text-sm text-foreground/60">
            Register a KOT printer and/or Bill printer per location — physical printing only fires
            on plans that include it.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm(true)}
          disabled={locations.length === 0}
          className="shrink-0 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-60"
        >
          + Add
        </button>
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {!isLoading && printers.length === 0 && (
        <p className="text-sm text-foreground/60">No printers registered yet.</p>
      )}
      {printers.length > 0 && (
        <ul className="flex flex-col gap-1.5 text-sm">
          {printers.map((p: Printer) => (
            <li key={p.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2">
              <span className="font-medium">{p.name}</span>
              <span className="text-xs uppercase text-foreground/50">{p.target}</span>
            </li>
          ))}
        </ul>
      )}

      <Link to="/admin/printers" className="mt-4 inline-block text-xs font-semibold text-accent hover:underline">
        Manage all printers →
      </Link>

      {showForm && (
        <PrinterFormModal editingPrinter={null} locations={locations} onClose={() => setShowForm(false)} />
      )}
    </div>
  );
}

function TaxTab() {
  const { data: rules = [], isLoading } = useQuery({ queryKey: ["tax-rules"], queryFn: listTaxRules });
  const [showForm, setShowForm] = useState(false);

  return (
    <div className="max-w-lg rounded-lg border border-border bg-surface p-5">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div>
          <h2 className="mb-1 text-base font-bold">Tax Rules</h2>
          <p className="text-sm text-foreground/60">
            CGST and SGST are always tracked as two separate rates, applied per your plan's tax mode.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowForm(true)}
          className="shrink-0 rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground"
        >
          + Add
        </button>
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {!isLoading && rules.length === 0 && (
        <p className="text-sm text-foreground/60">No tax rules yet.</p>
      )}
      {rules.length > 0 && (
        <ul className="flex flex-col gap-1.5 text-sm">
          {rules.map((r: TaxRule) => (
            <li key={r.id} className="flex items-center justify-between rounded-md border border-border px-3 py-2">
              <span className="font-medium">{r.name}</span>
              <span className="text-xs text-foreground/50">
                CGST {r.cgst_rate}% · SGST {r.sgst_rate}%
              </span>
            </li>
          ))}
        </ul>
      )}

      <Link to="/admin/tax-rules" className="mt-4 inline-block text-xs font-semibold text-accent hover:underline">
        Manage all tax rules →
      </Link>

      {showForm && <TaxRuleFormModal editingRule={null} onClose={() => setShowForm(false)} />}
    </div>
  );
}

function GeneralTab({ locationId }: { locationId: string }) {
  const queryClient = useQueryClient();
  const { data: hotel, isLoading } = useQuery({
    queryKey: ["hotel-master", locationId],
    queryFn: () => getHotelMaster(locationId),
  });

  const [form, setForm] = useState<HotelMasterUpdatePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedWarning, setSavedWarning] = useState<string | null>(null);

  useEffect(() => {
    if (hotel) {
      setForm({
        location_id: hotel.location_id,
        name: hotel.name ?? "",
        door_no: hotel.door_no ?? "",
        street: hotel.street ?? "",
        city: hotel.city ?? "",
        district: hotel.district ?? "",
        state: hotel.state ?? "Tamil Nadu",
        pincode: hotel.pincode ?? "",
        phone: hotel.phone ?? "",
        gstin: hotel.gstin ?? "",
        upi_id: hotel.upi_id ?? "",
        show_tamil_names: hotel.show_tamil_names,
        receipt_footer_message: hotel.receipt_footer_message ?? "",
      });
      setSavedWarning(hotel.gstin_state_warning);
    }
  }, [hotel]);

  const saveMutation = useMutation({
    mutationFn: (payload: HotelMasterUpdatePayload) => saveHotelMaster(payload),
    onSuccess: (updated) => {
      setSavedWarning(updated.gstin_state_warning);
      void queryClient.invalidateQueries({ queryKey: ["hotel-master", locationId] });
    },
    onError: (err) => setError(apiErrorMessage(err, "Failed to save Hotel Master.")),
  });

  const logoMutation = useMutation({
    mutationFn: (file: File) => uploadHotelMasterLogo(locationId, file),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["hotel-master", locationId] }),
    onError: (err) => setError(apiErrorMessage(err, "Failed to upload logo.")),
  });

  const removeLogoMutation = useMutation({
    mutationFn: () => removeHotelMasterLogo(locationId),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["hotel-master", locationId] }),
    onError: (err) => setError(apiErrorMessage(err, "Failed to remove logo.")),
  });

  function update<K extends keyof HotelMasterUpdatePayload>(key: K, value: HotelMasterUpdatePayload[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (form) saveMutation.mutate(form);
  }

  if (isLoading || !form) return <p className="text-sm text-foreground/60">Loading…</p>;

  // Recomputed from whatever's currently in the form (not just on GSTIN edits — a
  // State change alone can also create or resolve a mismatch) so the warning never
  // goes stale relative to what's on screen; the server-computed `savedWarning` is
  // only used as the very first render's value, before any local edit.
  const warning =
    form.gstin === (hotel?.gstin ?? "") && form.state === (hotel?.state ?? "")
      ? savedWarning
      : form.gstin
        ? gstinStateWarning(form.gstin, form.state ?? "")
        : null;

  return (
    <div className="grid max-w-4xl grid-cols-1 gap-6 lg:grid-cols-[1fr_320px]">
      <form onSubmit={handleSubmit} className="flex flex-col gap-5 rounded-lg border border-border bg-surface p-5">
        <fieldset className="flex flex-col gap-3">
          <legend className="mb-1 text-sm font-semibold">Hotel Master</legend>
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Name</label>
            <input
              required
              className={inputClass}
              value={form.name}
              onChange={(e) => update("name", e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Door No. / Building</label>
              <input
                className={inputClass}
                value={form.door_no ?? ""}
                onChange={(e) => update("door_no", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Street / Area</label>
              <input
                className={inputClass}
                value={form.street ?? ""}
                onChange={(e) => update("street", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>City</label>
              <input
                className={inputClass}
                value={form.city ?? ""}
                onChange={(e) => update("city", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>District</label>
              <input
                className={inputClass}
                value={form.district ?? ""}
                onChange={(e) => update("district", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>State</label>
              <select
                className={inputClass}
                value={form.state ?? ""}
                onChange={(e) => update("state", e.target.value)}
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
                value={form.pincode ?? ""}
                onChange={(e) => update("pincode", e.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Phone</label>
            <input
              className={inputClass}
              value={form.phone ?? ""}
              onChange={(e) => update("phone", e.target.value)}
            />
          </div>
        </fieldset>

        <fieldset className="flex flex-col gap-3">
          <legend className="mb-1 text-sm font-semibold">Tax & Payments</legend>
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>GSTIN</label>
            <input
              className={`${inputClass} uppercase`}
              maxLength={15}
              value={form.gstin ?? ""}
              onChange={(e) => update("gstin", e.target.value.toUpperCase())}
            />
            {warning && (
              <p className="rounded-md bg-gold/10 px-2.5 py-1.5 text-xs font-semibold text-gold">
                ⚠️ {warning}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>UPI ID (for bill QR code)</label>
            <input
              className={inputClass}
              placeholder="yourhotel@upi"
              value={form.upi_id ?? ""}
              onChange={(e) => update("upi_id", e.target.value)}
            />
          </div>
        </fieldset>

        <fieldset className="flex flex-col gap-2">
          <legend className="mb-1 text-sm font-semibold">Print</legend>
          <p className="text-xs text-foreground/50">
            The Tamil-names-on-print toggle for this location now lives in Settings &gt; Preferences.
          </p>

          <div className="mt-2 flex flex-col gap-1.5">
            <label className={labelClass}>Receipt Footer Message</label>
            <input
              className={inputClass}
              placeholder="Thank You & Visit Again..!!!"
              maxLength={200}
              value={form.receipt_footer_message ?? ""}
              onChange={(e) => update("receipt_footer_message", e.target.value)}
            />
            <p className="text-xs text-foreground/50">
              Printed centered near the end of the bill. Leave blank to use the default (&quot;Thank
              You &amp; Visit Again..!!!&quot;).
            </p>
          </div>

          <div className="mt-2 flex flex-col gap-1.5">
            <label className={labelClass}>Logo</label>
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) logoMutation.mutate(file);
              }}
              className="text-xs"
            />
            {logoMutation.isPending && <p className="text-xs text-foreground/50">Uploading…</p>}
            {hotel?.logo_url && (
              <button
                type="button"
                onClick={() => removeLogoMutation.mutate()}
                disabled={removeLogoMutation.isPending}
                className="self-start text-xs font-semibold text-chili hover:underline disabled:opacity-60"
              >
                {removeLogoMutation.isPending ? "Removing…" : "Remove logo"}
              </button>
            )}
          </div>
        </fieldset>

        {error && (
          <p role="alert" className="rounded-md bg-chili/10 px-3 py-2 text-sm text-chili">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={saveMutation.isPending}
          className="self-start rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-accent-foreground disabled:opacity-60"
        >
          {saveMutation.isPending ? "Saving…" : "Save Hotel Master"}
        </button>
      </form>

      <PrintPreview hotel={{ ...hotel, ...form } as HotelMaster} />
    </div>
  );
}

function PrintPreview({ hotel }: { hotel: HotelMaster }) {
  return (
    <div className="h-fit rounded-lg border border-border bg-surface p-4">
      <p className="mb-2 text-xs font-bold uppercase tracking-wide text-foreground/50">
        Bill Print Preview
      </p>
      <div className="rounded-md border border-dashed border-border bg-white p-4 text-center font-mono text-[11px] text-black">
        {hotel.logo_url ? (
          <img
            src={resolveAssetUrl(hotel.logo_url)}
            alt="Hotel logo"
            className="mx-auto mb-2 h-14 w-14 object-contain"
          />
        ) : (
          <div className="mx-auto mb-2 flex h-14 w-14 items-center justify-center rounded bg-gray-100 text-[9px] text-gray-400">
            No logo
          </div>
        )}
        <p className="font-bold">{hotel.name || "Hotel Name"}</p>
        {hotel.gstin && <p>GSTIN: {hotel.gstin}</p>}
        <div className="my-2 border-t border-dashed border-gray-400" />
        <p>2 x Meals{hotel.show_tamil_names ? " / சாப்பாடு" : ""}</p>
        <p>Grand Total: ₹200</p>
      </div>
    </div>
  );
}

function LocationsTab({ locations }: { locations: LocationDetail[] }) {
  const queryClient = useQueryClient();
  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: me });
  const [showForm, setShowForm] = useState<LocationDetail | "new" | null>(null);

  const activeCount = locations.filter((l) => l.is_active).length;
  const maxLocations = meData?.max_locations ?? 1;
  const atCap = activeCount >= maxLocations;

  const toggleActiveMutation = useMutation({
    mutationFn: (loc: LocationDetail) => updateLocation(loc.id, { is_active: !loc.is_active }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["managed-locations"] }),
  });

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <p className="text-sm text-foreground/60">
          {activeCount} / {maxLocations} location{maxLocations === 1 ? "" : "s"} used on your plan.
        </p>
        <button
          type="button"
          onClick={() => setShowForm("new")}
          disabled={atCap}
          title={atCap ? "Upgrade your plan to add another location" : undefined}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-40"
        >
          + Add Location
        </button>
      </div>
      {atCap && (
        <p className="mb-4 rounded-md bg-gold/10 px-3 py-2 text-sm text-gold">
          You've reached your plan's location limit. Upgrade to add another.
        </p>
      )}

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead className="bg-foreground/5 text-left text-xs uppercase tracking-wide text-foreground/60">
            <tr>
              <th className="px-4 py-2.5">Name</th>
              <th className="px-4 py-2.5">City</th>
              <th className="px-4 py-2.5">State</th>
              <th className="px-4 py-2.5">Status</th>
              <th className="px-4 py-2.5">Actions</th>
            </tr>
          </thead>
          <tbody>
            {locations.map((loc) => (
              <tr key={loc.id} className="border-t border-border">
                <td className="px-4 py-2.5 font-bold">{loc.name}</td>
                <td className="px-4 py-2.5 text-xs text-foreground/70">{loc.city ?? "—"}</td>
                <td className="px-4 py-2.5 text-xs text-foreground/70">{loc.state ?? "—"}</td>
                <td className="px-4 py-2.5">
                  <span
                    className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                      loc.is_active
                        ? "bg-accent/15 text-accent-foreground"
                        : "bg-foreground/10 text-foreground/50"
                    }`}
                  >
                    {loc.is_active ? "Active" : "Deactivated"}
                  </span>
                </td>
                <td className="px-4 py-2.5">
                  <div className="flex gap-3 text-xs font-semibold">
                    <button
                      type="button"
                      onClick={() => setShowForm(loc)}
                      className="text-accent hover:underline"
                    >
                      Edit
                    </button>
                    <button
                      type="button"
                      onClick={() => toggleActiveMutation.mutate(loc)}
                      disabled={!loc.is_active && atCap}
                      className={`disabled:opacity-40 ${
                        loc.is_active ? "text-chili hover:underline" : "text-accent hover:underline"
                      }`}
                    >
                      {loc.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {showForm && (
        <LocationFormModal editingLocation={showForm === "new" ? null : showForm} onClose={() => setShowForm(null)} />
      )}
    </div>
  );
}

function LocationFormModal({
  editingLocation,
  onClose,
}: {
  editingLocation: LocationDetail | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<LocationCreatePayload>(
    editingLocation
      ? {
          name: editingLocation.name,
          door_no: editingLocation.door_no ?? "",
          street: editingLocation.street ?? "",
          city: editingLocation.city ?? "",
          district: editingLocation.district ?? "",
          state: editingLocation.state ?? "Tamil Nadu",
          pincode: editingLocation.pincode ?? "",
          phone: editingLocation.phone ?? "",
        }
      : {
          name: "",
          door_no: "",
          street: "",
          city: "",
          district: "",
          state: "Tamil Nadu",
          pincode: "",
          phone: "",
        },
  );
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      editingLocation ? updateLocation(editingLocation.id, form) : createLocation(form),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["managed-locations"] });
      void queryClient.invalidateQueries({ queryKey: ["tenant-locations"] });
      onClose();
    },
    onError: (err) => setError(apiErrorMessage(err, "Failed to save location.")),
  });

  function update<K extends keyof LocationCreatePayload>(key: K, value: LocationCreatePayload[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    mutation.mutate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-lg rounded-lg bg-background p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-bold">{editingLocation ? "Edit Location" : "Add Location"}</h2>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Name</label>
            <input
              required
              placeholder="e.g. Anna Nagar Branch"
              className={inputClass}
              value={form.name}
              onChange={(e) => update("name", e.target.value)}
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Door No. / Building</label>
              <input
                className={inputClass}
                value={form.door_no ?? ""}
                onChange={(e) => update("door_no", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Street / Area</label>
              <input
                className={inputClass}
                value={form.street ?? ""}
                onChange={(e) => update("street", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>City</label>
              <input
                className={inputClass}
                value={form.city ?? ""}
                onChange={(e) => update("city", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>District</label>
              <input
                className={inputClass}
                value={form.district ?? ""}
                onChange={(e) => update("district", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>State</label>
              <select
                className={inputClass}
                value={form.state ?? ""}
                onChange={(e) => update("state", e.target.value)}
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
                value={form.pincode ?? ""}
                onChange={(e) => update("pincode", e.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-col gap-1.5">
            <label className={labelClass}>Phone</label>
            <input
              className={inputClass}
              value={form.phone ?? ""}
              onChange={(e) => update("phone", e.target.value)}
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
              {mutation.isPending ? "Saving…" : editingLocation ? "Save Changes" : "Add Location"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
