import { useTranslation } from "react-i18next";

import { Modal } from "@/components/ui/Modal";
import type { Bill } from "@/types/bill";
import { formatPaise } from "@/utils/money";

export interface SavedBillDetailModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  bill: Bill | null;
  isLoading: boolean;
}

/** Read-only detail view opened from the saved bill search — shows every
 * line item and the server-computed totals for a past bill without
 * touching the live cart, unlike F9 resume (which is destructive/editable). */
export function SavedBillDetailModal({ open, onOpenChange, bill, isLoading }: SavedBillDetailModalProps) {
  const { t } = useTranslation();

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={bill ? t("pos.viewingBillTitle", { number: bill.bill_number }) : t("common.loading")}
      className="max-w-2xl"
    >
      {isLoading && <p className="text-sm text-slate-500">{t("common.loading")}</p>}

      {bill && (
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600">
            <span>{new Date(bill.created_at).toLocaleString("en-IN")}</span>
            <span>{t(`pos.billStatus.${bill.status}`)}</span>
          </div>
          {(bill.customer_name || bill.customer_phone) && (
            <p className="text-sm text-slate-600">
              {bill.customer_name}
              {bill.customer_name && bill.customer_phone ? " · " : ""}
              {bill.customer_phone}
            </p>
          )}

          <div className="rounded-xl border border-slate-200 bg-white">
            <ul className="divide-y divide-slate-100">
              {bill.items.map((line) => (
                <li key={line.id} className="flex items-center justify-between gap-3 px-4 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-slate-900">{line.item_name_snapshot}</p>
                    <p className="text-sm text-slate-500">
                      {line.qty} × {formatPaise(line.unit_price_paise)}
                      {line.discount_paise > 0 && (
                        <span className="ml-2 text-brand-600">-{formatPaise(line.discount_paise)}</span>
                      )}
                    </p>
                  </div>
                  <div className="shrink-0 font-medium text-slate-900">
                    {formatPaise(line.line_total_paise)}
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-1.5 text-sm">
            <Row label={t("pos.subtotal")} value={formatPaise(bill.subtotal_paise)} />
            {bill.discount_paise > 0 && (
              <Row label={t("pos.discount")} value={`-${formatPaise(bill.discount_paise)}`} />
            )}
            <Row label={t("pos.cgst")} value={formatPaise(bill.cgst_paise)} />
            <Row label={t("pos.sgst")} value={formatPaise(bill.sgst_paise)} />
            {bill.round_off_paise !== 0 && (
              <Row
                label={t("pos.roundOff")}
                value={`${bill.round_off_paise > 0 ? "+" : ""}${formatPaise(bill.round_off_paise)}`}
              />
            )}
            <div className="my-2 border-t border-slate-200" />
            <div className="flex items-center justify-between text-base font-semibold text-slate-900">
              <span>{t("pos.total")}</span>
              <span>{formatPaise(bill.total_paise)}</span>
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-slate-600">{label}</span>
      <span className="font-medium text-slate-800">{value}</span>
    </div>
  );
}
