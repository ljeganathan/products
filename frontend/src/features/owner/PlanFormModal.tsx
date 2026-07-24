import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import type { Plan, PlanUpdate } from "@/types/plan";

export interface PlanFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plan: Plan | null;
  onSubmit: (payload: PlanUpdate) => Promise<void>;
  isSubmitting: boolean;
}

const FEATURE_KEYS = ["low_stock_alerts", "multi_store", "dashboard_range", "discount_rules_advanced", "api_access"] as const;

function unlimitedAwareToString(value: number): string {
  return String(value);
}

export function PlanFormModal({ open, onOpenChange, plan, onSubmit, isSubmitting }: PlanFormModalProps) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [priceRupees, setPriceRupees] = useState("0");
  const [maxUsers, setMaxUsers] = useState("2");
  const [maxStores, setMaxStores] = useState("1");
  const [maxPrinterProfiles, setMaxPrinterProfiles] = useState("1");
  const [savedBillDays, setSavedBillDays] = useState("7");
  const [features, setFeatures] = useState<Record<string, boolean>>({});

  useEffect(() => {
    if (!open || !plan) return;
    setName(plan.name);
    setPriceRupees((plan.price_paise / 100).toString());
    setMaxUsers(unlimitedAwareToString(plan.max_users));
    setMaxStores(unlimitedAwareToString(plan.max_stores));
    setMaxPrinterProfiles(unlimitedAwareToString(plan.max_printer_profiles));
    setSavedBillDays(unlimitedAwareToString(plan.saved_bill_days));
    setFeatures(plan.features_json);
  }, [open, plan]);

  async function handleSubmit() {
    await onSubmit({
      name: name.trim(),
      price_paise: Math.round((Number(priceRupees) || 0) * 100),
      max_users: Number(maxUsers),
      max_stores: Number(maxStores),
      max_printer_profiles: Number(maxPrinterProfiles),
      saved_bill_days: Number(savedBillDays),
      low_stock_alerts: Boolean(features.low_stock_alerts),
      features_json: features,
    });
  }

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={t("owner.plans.editTitle", { name: plan?.name })}
      footer={
        <Button onClick={() => void handleSubmit()} isLoading={isSubmitting}>
          {t("common.save")}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <Input label={t("owner.plans.name")} value={name} onChange={(e) => setName(e.target.value)} />
        <Input
          type="number"
          min="0"
          label={t("owner.plans.priceMonthly")}
          value={priceRupees}
          onChange={(e) => setPriceRupees(e.target.value)}
        />
        <div className="grid grid-cols-3 gap-4">
          <Input
            type="number"
            label={t("owner.plans.maxUsers")}
            value={maxUsers}
            onChange={(e) => setMaxUsers(e.target.value)}
          />
          <Input
            type="number"
            label={t("owner.plans.maxStores")}
            value={maxStores}
            onChange={(e) => setMaxStores(e.target.value)}
          />
          <Input
            type="number"
            label={t("owner.plans.maxPrinterProfiles")}
            value={maxPrinterProfiles}
            onChange={(e) => setMaxPrinterProfiles(e.target.value)}
          />
        </div>
        <Input
          type="number"
          label={t("owner.plans.savedBillDays")}
          value={savedBillDays}
          onChange={(e) => setSavedBillDays(e.target.value)}
        />
        <p className="text-xs text-slate-500">{t("owner.plans.unlimitedHint")}</p>

        <div className="border-t border-slate-200 pt-4">
          <p className="mb-2 text-sm font-medium text-slate-700">{t("owner.plans.features")}</p>
          <div className="flex flex-col gap-2">
            {FEATURE_KEYS.map((key) => (
              <label key={key} className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={Boolean(features[key])}
                  onChange={(e) => setFeatures((prev) => ({ ...prev, [key]: e.target.checked }))}
                  className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                />
                {t(`owner.plans.featureKeys.${key}`)}
              </label>
            ))}
          </div>
        </div>
      </div>
    </Modal>
  );
}
