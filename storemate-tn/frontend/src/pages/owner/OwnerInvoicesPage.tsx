import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { generateInvoice, listInvoices, updateInvoiceStatus } from "@/api/platformInvoices";
import { listSubscriptions } from "@/api/platformSubscriptions";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { Table, type Column } from "@/components/ui/Table";
import { GenerateInvoiceModal } from "@/features/owner/GenerateInvoiceModal";
import { toast } from "@/store/toastStore";
import type { Invoice, InvoiceStatus } from "@/types/invoice";
import { getApiErrorMessage } from "@/utils/apiError";
import { formatPaise } from "@/utils/money";

const STATUS_VARIANT: Record<InvoiceStatus, "success" | "warning" | "danger" | "neutral"> = {
  paid: "success",
  pending: "warning",
  failed: "danger",
  void: "neutral",
};

export default function OwnerInvoicesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["platform-invoices", page],
    queryFn: () => listInvoices({ page, page_size: 20 }),
  });

  const { data: subscriptions } = useQuery({
    queryKey: ["platform-subscriptions-all"],
    queryFn: () => listSubscriptions({ page: 1, page_size: 100 }),
  });

  async function invalidate() {
    await queryClient.invalidateQueries({ queryKey: ["platform-invoices"] });
  }

  async function handleGenerate(subscriptionId: string) {
    setIsGenerating(true);
    try {
      await generateInvoice({ subscription_id: subscriptionId });
      await invalidate();
      setGenerateOpen(false);
      toast("success", t("owner.invoices.generated"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleUpdateStatus(invoice: Invoice, status: InvoiceStatus) {
    setUpdatingId(invoice.id);
    try {
      await updateInvoiceStatus(invoice.id, { status });
      await invalidate();
      toast("success", t("common.saved"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setUpdatingId(null);
    }
  }

  const columns: Column<Invoice>[] = [
    { key: "number", header: t("owner.invoices.invoiceNumber"), render: (inv) => inv.invoice_number },
    { key: "tenant", header: t("owner.tenants.storeName"), render: (inv) => inv.tenant_name },
    {
      key: "amount",
      header: t("owner.invoices.amount"),
      render: (inv) => formatPaise(inv.amount_paise + inv.gst_paise),
    },
    {
      key: "status",
      header: t("common.status"),
      render: (inv) => (
        <Badge variant={STATUS_VARIANT[inv.status]}>{t(`owner.invoices.statuses.${inv.status}`)}</Badge>
      ),
    },
    {
      key: "issued",
      header: t("owner.invoices.issuedAt"),
      render: (inv) => new Date(inv.issued_at).toLocaleDateString(),
    },
    {
      key: "actions",
      header: t("common.actions"),
      render: (inv) =>
        inv.status === "pending" ? (
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              isLoading={updatingId === inv.id}
              onClick={() => void handleUpdateStatus(inv, "paid")}
            >
              {t("owner.invoices.markPaid")}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              isLoading={updatingId === inv.id}
              onClick={() => void handleUpdateStatus(inv, "failed")}
            >
              {t("owner.invoices.markOverdue")}
            </Button>
          </div>
        ) : (
          "—"
        ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("owner.invoices.title")}
        subtitle={t("owner.invoices.subtitle")}
        actions={
          <Button onClick={() => setGenerateOpen(true)}>
            <Plus className="h-4 w-4" />
            {t("owner.invoices.generateButton")}
          </Button>
        }
      />

      <Table
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(inv) => inv.id}
        isLoading={isLoading}
        emptyMessage={t("owner.invoices.empty")}
        page={page}
        pageSize={20}
        total={data?.total}
        onPageChange={setPage}
      />

      <GenerateInvoiceModal
        open={generateOpen}
        onOpenChange={setGenerateOpen}
        subscriptions={subscriptions?.items ?? []}
        onSubmit={handleGenerate}
        isSubmitting={isGenerating}
      />
    </div>
  );
}
