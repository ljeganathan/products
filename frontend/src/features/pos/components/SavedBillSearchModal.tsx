import { useQuery } from "@tanstack/react-query";
import { Lock } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { searchBills } from "@/api/bills";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Table, type Column } from "@/components/ui/Table";
import type { Bill } from "@/types/bill";
import { formatPaise } from "@/utils/money";

export interface SavedBillSearchModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onViewBill: (bill: Bill) => void;
}

export function SavedBillSearchModal({ open, onOpenChange, onViewBill }: SavedBillSearchModalProps) {
  const { t } = useTranslation();
  const [billNumber, setBillNumber] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [customerPhone, setCustomerPhone] = useState("");
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["saved-bills", billNumber, dateFrom, customerPhone, page],
    queryFn: () =>
      searchBills({
        page,
        page_size: 10,
        bill_number: billNumber ? Number(billNumber) : undefined,
        date_from: dateFrom || undefined,
        customer_phone: customerPhone || undefined,
      }),
    enabled: open,
  });

  const columns: Column<Bill>[] = [
    {
      key: "bill_number",
      header: t("pos.billNumberColumn"),
      render: (b) => (
        <button
          type="button"
          onClick={() => onViewBill(b)}
          className="font-medium text-brand-600 underline-offset-2 hover:underline"
        >
          #{b.bill_number}
        </button>
      ),
    },
    {
      key: "created_at",
      header: t("pos.dateColumn"),
      render: (b) => new Date(b.created_at).toLocaleString("en-IN"),
    },
    { key: "customer", header: t("pos.customerColumn"), render: (b) => b.customer_name ?? "—" },
    { key: "status", header: t("pos.statusColumn"), render: (b) => t(`pos.billStatus.${b.status}`) },
    { key: "total", header: t("pos.totalColumn"), render: (b) => formatPaise(b.total_paise) },
  ];

  return (
    <Modal open={open} onOpenChange={onOpenChange} title={t("pos.savedBillSearchTitle")} className="max-w-3xl">
      <div className="flex flex-col gap-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <Input
            label={t("pos.billNumberColumn")}
            type="number"
            value={billNumber}
            onChange={(e) => setBillNumber(e.target.value)}
          />
          <Input
            label={t("pos.dateFromLabel")}
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
          />
          <Input
            label={t("pos.customerColumn")}
            value={customerPhone}
            onChange={(e) => setCustomerPhone(e.target.value)}
          />
        </div>

        {data && data.requested_from_clamped && (
          <div className="flex items-center gap-2 rounded-lg border border-warning-200 bg-warning-50 px-3 py-2 text-sm text-warning-800">
            <Lock className="h-4 w-4 shrink-0" />
            <span>
              {t("pos.savedBillWindowExceeded", {
                days: data.saved_bill_days,
                date: data.window_start,
              })}
            </span>
          </div>
        )}
        {data && !data.requested_from_clamped && data.saved_bill_days !== -1 && (
          <p className="text-sm text-slate-500">
            {t("pos.savedBillWindowNote", { days: data.saved_bill_days })}
          </p>
        )}

        <Table
          columns={columns}
          rows={data?.items ?? []}
          rowKey={(b) => b.id}
          isLoading={isLoading}
          page={page}
          pageSize={10}
          total={data?.total}
          onPageChange={setPage}
        />
      </div>
    </Modal>
  );
}
