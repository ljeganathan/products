import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import type { Category } from "@/types/category";
import type { DiscountRuleCreate, DiscountScope } from "@/types/discountRule";
import type { DiscountType } from "@/types/bill";
import type { Item } from "@/types/item";

export interface DiscountRuleFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: Item[];
  categories: Category[];
  onSubmit: (payload: DiscountRuleCreate) => Promise<void>;
  isSubmitting: boolean;
}

export function DiscountRuleFormModal({
  open,
  onOpenChange,
  items,
  categories,
  onSubmit,
  isSubmitting,
}: DiscountRuleFormModalProps) {
  const { t } = useTranslation();
  const [scope, setScope] = useState<DiscountScope>("bill");
  const [targetId, setTargetId] = useState("");
  const [type, setType] = useState<DiscountType>("percent");
  const [value, setValue] = useState("");
  const [startsAt, setStartsAt] = useState("");
  const [endsAt, setEndsAt] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setScope("bill");
    setTargetId("");
    setType("percent");
    setValue("");
    setStartsAt("");
    setEndsAt("");
    setError(null);
  }, [open]);

  async function handleSubmit() {
    const parsed = Number(value);
    if (!value || Number.isNaN(parsed) || parsed <= 0) {
      setError(t("settings.discounts.valueRequired"));
      return;
    }
    if (scope !== "bill" && !targetId) {
      setError(t("settings.discounts.targetRequired"));
      return;
    }
    setError(null);
    await onSubmit({
      scope,
      target_id: scope === "bill" ? null : targetId,
      type,
      value: Math.round(parsed * 100),
      starts_at: startsAt ? new Date(startsAt).toISOString() : null,
      ends_at: endsAt ? new Date(endsAt).toISOString() : null,
      is_active: true,
    });
  }

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={t("settings.discounts.addTitle")}
      footer={
        <Button onClick={() => void handleSubmit()} isLoading={isSubmitting}>
          {t("common.save")}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <Select label={t("settings.discounts.scope")} value={scope} onChange={(e) => setScope(e.target.value as DiscountScope)}>
          <option value="bill">{t("settings.discounts.scopes.bill")}</option>
          <option value="item">{t("settings.discounts.scopes.item")}</option>
          <option value="category">{t("settings.discounts.scopes.category")}</option>
        </Select>

        {scope === "item" && (
          <Select
            label={t("settings.discounts.selectItem")}
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
          >
            <option value="">{t("settings.discounts.chooseOne")}</option>
            {items.map((i) => (
              <option key={i.id} value={i.id}>
                {i.name_en}
              </option>
            ))}
          </Select>
        )}
        {scope === "category" && (
          <Select
            label={t("settings.discounts.selectCategory")}
            value={targetId}
            onChange={(e) => setTargetId(e.target.value)}
          >
            <option value="">{t("settings.discounts.chooseOne")}</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name_en}
              </option>
            ))}
          </Select>
        )}

        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setType("flat")}
            className={`h-11 rounded-lg border text-sm font-medium ${
              type === "flat" ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 text-slate-700"
            }`}
          >
            {t("pos.discountFlat")}
          </button>
          <button
            type="button"
            onClick={() => setType("percent")}
            className={`h-11 rounded-lg border text-sm font-medium ${
              type === "percent" ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 text-slate-700"
            }`}
          >
            {t("pos.discountPercent")}
          </button>
        </div>
        <Input
          type="number"
          min="0"
          step="0.01"
          label={type === "flat" ? t("pos.discountAmountLabel") : t("pos.discountPercentLabel")}
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />

        <div className="grid grid-cols-2 gap-4">
          <Input
            type="date"
            label={t("settings.discounts.startsAt")}
            value={startsAt}
            onChange={(e) => setStartsAt(e.target.value)}
          />
          <Input
            type="date"
            label={t("settings.discounts.endsAt")}
            value={endsAt}
            onChange={(e) => setEndsAt(e.target.value)}
          />
        </div>

        {error && <p className="text-sm text-danger-600">{error}</p>}
      </div>
    </Modal>
  );
}
