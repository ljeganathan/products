import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import type { Subscription } from "@/types/subscription";

export interface GenerateInvoiceModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  subscriptions: Subscription[];
  onSubmit: (subscriptionId: string) => Promise<void>;
  isSubmitting: boolean;
}

export function GenerateInvoiceModal({
  open,
  onOpenChange,
  subscriptions,
  onSubmit,
  isSubmitting,
}: GenerateInvoiceModalProps) {
  const { t } = useTranslation();
  const [subscriptionId, setSubscriptionId] = useState("");

  useEffect(() => {
    if (open) setSubscriptionId(subscriptions[0]?.id ?? "");
  }, [open, subscriptions]);

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={t("owner.invoices.generateTitle")}
      footer={
        <Button
          onClick={() => void onSubmit(subscriptionId)}
          isLoading={isSubmitting}
          disabled={!subscriptionId}
        >
          {t("owner.invoices.generateButton")}
        </Button>
      }
    >
      <Select
        label={t("owner.invoices.selectTenant")}
        value={subscriptionId}
        onChange={(e) => setSubscriptionId(e.target.value)}
      >
        {subscriptions.map((sub) => (
          <option key={sub.id} value={sub.id}>
            {sub.tenant_name} — {t(`plans.${sub.plan_code}`)}
          </option>
        ))}
      </Select>
    </Modal>
  );
}
