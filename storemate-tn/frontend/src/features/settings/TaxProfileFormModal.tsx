import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import type { TaxProfile, TaxProfileCreate } from "@/types/item";
import { cn } from "@/utils/cn";

const TN_SLABS = [0, 5, 12, 18, 28];

/** Mirrors the backend's check_tax_slab_warning (services/tax_profile_service.py)
 * for instant feedback while editing — the server remains authoritative and
 * re-validates on save regardless. */
function slabWarning(
  cgstPct: number,
  sgstPct: number,
  t: (key: string, opts?: Record<string, unknown>) => string,
): string | null {
  const total = Math.round((cgstPct + sgstPct) * 100) / 100;
  if (TN_SLABS.includes(total)) return null;
  return t("settings.tax.slabWarning", { total, slabs: TN_SLABS.map((s) => `${s}%`).join(", ") });
}

export interface TaxProfileFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  profile: TaxProfile | null;
  onSubmit: (payload: TaxProfileCreate) => Promise<void>;
  isSubmitting: boolean;
}

export function TaxProfileFormModal({
  open,
  onOpenChange,
  profile,
  onSubmit,
  isSubmitting,
}: TaxProfileFormModalProps) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [cgstPct, setCgstPct] = useState("0");
  const [sgstPct, setSgstPct] = useState("0");
  const [isDefault, setIsDefault] = useState(false);
  const [selectedSlab, setSelectedSlab] = useState<number | null>(0);

  useEffect(() => {
    if (!open) return;
    setName(profile?.name ?? "");
    setCgstPct(String(profile?.cgst_pct ?? 0));
    setSgstPct(String(profile?.sgst_pct ?? 0));
    setIsDefault(profile?.is_default ?? false);
    const total = (profile?.cgst_pct ?? 0) + (profile?.sgst_pct ?? 0);
    setSelectedSlab(TN_SLABS.includes(total) ? total : null);
  }, [open, profile]);

  function applySlab(slab: number) {
    setSelectedSlab(slab);
    setCgstPct(String(slab / 2));
    setSgstPct(String(slab / 2));
  }

  async function handleSubmit() {
    await onSubmit({
      name: name.trim(),
      cgst_pct: Number(cgstPct) || 0,
      sgst_pct: Number(sgstPct) || 0,
      is_default: isDefault,
    });
  }

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={profile ? t("settings.tax.editTitle") : t("settings.tax.addTitle")}
      footer={
        <Button onClick={() => void handleSubmit()} isLoading={isSubmitting}>
          {t("common.save")}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <Input label={t("settings.tax.name")} value={name} onChange={(e) => setName(e.target.value)} />

        <div>
          <label className="mb-1.5 block text-sm font-medium text-slate-700">
            {t("settings.tax.slabPreset")}
          </label>
          <div className="grid grid-cols-5 gap-1.5">
            {TN_SLABS.map((slab) => (
              <button
                key={slab}
                type="button"
                onClick={() => applySlab(slab)}
                className={cn(
                  "h-11 rounded-lg border text-sm font-medium",
                  selectedSlab === slab
                    ? "border-brand-600 bg-brand-600 text-white"
                    : "border-slate-300 text-slate-700",
                )}
              >
                {slab}%
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <Input
            type="number"
            min="0"
            max="100"
            step="0.01"
            label={t("settings.tax.cgstPct")}
            value={cgstPct}
            onChange={(e) => {
              setCgstPct(e.target.value);
              setSelectedSlab(null);
            }}
          />
          <Input
            type="number"
            min="0"
            max="100"
            step="0.01"
            label={t("settings.tax.sgstPct")}
            value={sgstPct}
            onChange={(e) => {
              setSgstPct(e.target.value);
              setSelectedSlab(null);
            }}
          />
        </div>

        {slabWarning(Number(cgstPct) || 0, Number(sgstPct) || 0, t) && (
          <p className="rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-800">
            {slabWarning(Number(cgstPct) || 0, Number(sgstPct) || 0, t)}
          </p>
        )}

        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={isDefault}
            onChange={(e) => setIsDefault(e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          {t("settings.tax.setDefault")}
        </label>
      </div>
    </Modal>
  );
}
