import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { searchBills } from "@/api/bills";
import { EmptyState } from "@/components/ui/EmptyState";
import { Modal } from "@/components/ui/Modal";
import { formatPaise } from "@/utils/money";

export interface HeldBillsModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onResume: (billId: string) => void;
}

export function HeldBillsModal({ open, onOpenChange, onResume }: HeldBillsModalProps) {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: ["held-bills"],
    queryFn: () => searchBills({ status: "held", page_size: 50 }),
    enabled: open,
  });

  const heldBills = data?.items ?? [];

  return (
    <Modal open={open} onOpenChange={onOpenChange} title={t("pos.heldBillsTitle")}>
      {isLoading && <p className="text-slate-500">{t("common.loading")}</p>}
      {!isLoading && heldBills.length === 0 && (
        <EmptyState title={t("pos.noHeldBills")} />
      )}
      {!isLoading && heldBills.length > 0 && (
        <ul className="divide-y divide-slate-100">
          {heldBills.map((bill) => (
            <li key={bill.id}>
              <button
                type="button"
                onClick={() => onResume(bill.id)}
                className="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-3 text-left hover:bg-slate-50"
              >
                <div>
                  <p className="font-medium text-slate-900">
                    {t("pos.billNumber", { number: bill.bill_number })}
                  </p>
                  <p className="text-sm text-slate-500">
                    {new Date(bill.created_at).toLocaleTimeString("en-IN", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                    {bill.customer_name ? ` · ${bill.customer_name}` : ""}
                  </p>
                </div>
                <span className="font-semibold text-slate-900">{formatPaise(bill.total_paise)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </Modal>
  );
}
