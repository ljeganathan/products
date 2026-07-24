import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import type { Subscription, SubscriptionUpdate } from "@/types/subscription";

export interface AddOnFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  subscription: Subscription | null;
  onSubmit: (payload: SubscriptionUpdate) => Promise<void>;
  isSubmitting: boolean;
}

export function AddOnFormModal({
  open,
  onOpenChange,
  subscription,
  onSubmit,
  isSubmitting,
}: AddOnFormModalProps) {
  const { t } = useTranslation();
  const [extraUsers, setExtraUsers] = useState("0");
  const [extraStores, setExtraStores] = useState("0");

  useEffect(() => {
    if (!open || !subscription) return;
    setExtraUsers(String(subscription.extra_users));
    setExtraStores(String(subscription.extra_stores));
  }, [open, subscription]);

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={t("owner.subscriptions.addOnsTitle", { name: subscription?.tenant_name })}
      footer={
        <Button
          onClick={() =>
            void onSubmit({ extra_users: Number(extraUsers) || 0, extra_stores: Number(extraStores) || 0 })
          }
          isLoading={isSubmitting}
        >
          {t("common.save")}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <Input
          type="number"
          min="0"
          label={t("owner.subscriptions.extraUsers")}
          value={extraUsers}
          onChange={(e) => setExtraUsers(e.target.value)}
        />
        <Input
          type="number"
          min="0"
          label={t("owner.subscriptions.extraStores")}
          value={extraStores}
          onChange={(e) => setExtraStores(e.target.value)}
        />
        <p className="text-xs text-slate-500">{t("owner.subscriptions.addOnsHint")}</p>
      </div>
    </Modal>
  );
}
