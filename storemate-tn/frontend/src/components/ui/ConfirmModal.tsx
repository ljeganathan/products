import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";

export interface ConfirmModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  body?: string;
  confirmLabel?: string;
  isConfirming?: boolean;
  onConfirm: () => void;
  danger?: boolean;
}

export function ConfirmModal({
  open,
  onOpenChange,
  title,
  description,
  body,
  confirmLabel,
  isConfirming = false,
  onConfirm,
  danger = true,
}: ConfirmModalProps) {
  const { t } = useTranslation();

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      footer={
        <>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
          <Button
            variant={danger ? "danger" : "primary"}
            onClick={onConfirm}
            isLoading={isConfirming}
          >
            {confirmLabel ?? t("common.confirm")}
          </Button>
        </>
      }
    >
      {body && <p className="text-sm text-slate-500">{body}</p>}
    </Modal>
  );
}
