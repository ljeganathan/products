import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import type { AvailablePlan } from "@/types/subscriptionView";

export interface UpgradeRequestModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plans: AvailablePlan[];
  currentPlanCode: string;
  onSubmit: (planId: string) => Promise<void>;
  isSubmitting: boolean;
}

export function UpgradeRequestModal({
  open,
  onOpenChange,
  plans,
  currentPlanCode,
  onSubmit,
  isSubmitting,
}: UpgradeRequestModalProps) {
  const { t } = useTranslation();
  const selectablePlans = plans.filter((p) => p.code !== currentPlanCode);
  const [planId, setPlanId] = useState(selectablePlans[0]?.id ?? "");

  useEffect(() => {
    if (open) setPlanId(selectablePlans[0]?.id ?? "");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- selectablePlans is derived fresh each render
  }, [open]);

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={t("settings.subscription.upgradeRequestTitle")}
      footer={
        <Button onClick={() => void onSubmit(planId)} isLoading={isSubmitting} disabled={!planId}>
          {t("settings.subscription.sendRequest")}
        </Button>
      }
    >
      <div className="flex flex-col gap-3">
        <Select
          label={t("settings.subscription.requestedPlan")}
          value={planId}
          onChange={(e) => setPlanId(e.target.value)}
        >
          {selectablePlans.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </Select>
        <p className="text-xs text-slate-500">{t("settings.subscription.upgradeRequestHint")}</p>
      </div>
    </Modal>
  );
}
