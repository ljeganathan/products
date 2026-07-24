import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import type { Plan } from "@/types/plan";

export interface ChangePlanModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tenantName: string;
  currentPlanId: string;
  plans: Plan[];
  onSubmit: (planId: string) => Promise<void>;
  isSubmitting: boolean;
}

export function ChangePlanModal({
  open,
  onOpenChange,
  tenantName,
  currentPlanId,
  plans,
  onSubmit,
  isSubmitting,
}: ChangePlanModalProps) {
  const { t } = useTranslation();
  const [planId, setPlanId] = useState(currentPlanId);

  useEffect(() => {
    if (open) setPlanId(currentPlanId);
  }, [open, currentPlanId]);

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={t("owner.subscriptions.changePlanTitle", { name: tenantName })}
      footer={
        <Button onClick={() => void onSubmit(planId)} isLoading={isSubmitting} disabled={planId === currentPlanId}>
          {t("owner.subscriptions.applyChange")}
        </Button>
      }
    >
      <Select label={t("owner.tenants.plan")} value={planId} onChange={(e) => setPlanId(e.target.value)}>
        {plans.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </Select>
    </Modal>
  );
}
