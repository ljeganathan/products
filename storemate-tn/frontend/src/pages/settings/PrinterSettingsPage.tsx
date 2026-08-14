import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bluetooth, Pencil, Plus, Printer, Trash2 } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getCompanySettings } from "@/api/companySettings";
import {
  createPrinterProfile,
  deletePrinterProfile,
  listPrinterProfiles,
  updatePrinterProfile,
} from "@/api/printerProfiles";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { PageHeader } from "@/components/ui/PageHeader";
import { dispatchPrint } from "@/features/pos/printDispatch";
import { PrinterProfileFormModal } from "@/features/settings/PrinterProfileFormModal";
import { buildSampleReceiptPayload } from "@/features/settings/sampleReceipt";
import { toast } from "@/store/toastStore";
import type { PrinterProfile, PrinterProfileCreate } from "@/types/printer";
import { getApiErrorMessage } from "@/utils/apiError";
import { pairBluetoothPrinter } from "@/utils/webBluetoothPrinter";

function connectionDetailSummary(profile: PrinterProfile): string | null {
  if ((profile.connection === "network" || profile.connection === "wifi") && profile.connection_details.ip) {
    return `${profile.connection_details.ip}:${profile.connection_details.port || "9100"}`;
  }
  if (profile.connection === "bluetooth") {
    return profile.connection_details.bluetooth_device_name ?? null;
  }
  return null;
}

export default function PrinterSettingsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<PrinterProfile | null>(null);
  const [deleting, setDeleting] = useState<PrinterProfile | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [testPrintingId, setTestPrintingId] = useState<string | null>(null);
  const [repairingId, setRepairingId] = useState<string | null>(null);

  const { data: profiles, isLoading } = useQuery({
    queryKey: ["printer-profiles-all"],
    queryFn: () => listPrinterProfiles(),
  });

  async function handleSubmit(payload: PrinterProfileCreate) {
    setIsSubmitting(true);
    try {
      if (editing) {
        await updatePrinterProfile(editing.id, payload);
      } else {
        await createPrinterProfile(payload);
      }
      await queryClient.invalidateQueries({ queryKey: ["printer-profiles-all"] });
      await queryClient.invalidateQueries({ queryKey: ["printer-profiles"] });
      setFormOpen(false);
      toast("success", t("common.saved"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!deleting) return;
    setIsDeleting(true);
    try {
      await deletePrinterProfile(deleting.id);
      await queryClient.invalidateQueries({ queryKey: ["printer-profiles-all"] });
      setDeleting(null);
      toast("success", t("common.deleted"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsDeleting(false);
    }
  }

  async function handleRepair(profile: PrinterProfile) {
    setRepairingId(profile.id);
    try {
      const paired = await pairBluetoothPrinter();
      await updatePrinterProfile(profile.id, {
        connection_details: {
          bluetooth_device_id: paired.bluetooth_device_id,
          bluetooth_device_name: paired.bluetooth_device_name,
        },
      });
      await queryClient.invalidateQueries({ queryKey: ["printer-profiles-all"] });
      await queryClient.invalidateQueries({ queryKey: ["printer-profiles"] });
      toast("success", t("settings.printer.pairSuccess", { name: paired.bluetooth_device_name }));
    } catch (err) {
      toast("danger", err instanceof Error ? err.message : t("settings.printer.pairError"));
    } finally {
      setRepairingId(null);
    }
  }

  async function handleTestPrint(profile: PrinterProfile) {
    setTestPrintingId(profile.id);
    try {
      const company = await getCompanySettings();
      const payload = buildSampleReceiptPayload(company);
      await dispatchPrint(profile, payload);
      toast("success", t("pos.printSuccessTitle"));
    } catch (err) {
      toast("danger", t("pos.printFailedTitle"), getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setTestPrintingId(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title={t("settings.printer.title")}
        subtitle={t("settings.printer.subtitle")}
        actions={
          <Button
            onClick={() => {
              setEditing(null);
              setFormOpen(true);
            }}
          >
            <Plus className="h-4 w-4" />
            {t("settings.printer.addButton")}
          </Button>
        }
      />

      {isLoading && <p className="text-slate-500">{t("common.loading")}</p>}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {profiles?.map((p) => (
          <div key={p.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-card">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium text-slate-900">{p.name}</p>
                <p className="mt-1 text-sm text-slate-500">
                  {t(`settings.printer.types.${p.type}`)} · {p.paper_width_chars} {t("settings.printer.chars")}
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  {t(`settings.printer.connections.${p.connection}`)}
                  {connectionDetailSummary(p) ? ` · ${connectionDetailSummary(p)}` : ""}
                </p>
              </div>
              {p.is_default && <Badge variant="success">{t("settings.tax.default")}</Badge>}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => {
                  setEditing(p);
                  setFormOpen(true);
                }}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
                aria-label={t("common.edit")}
              >
                <Pencil className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => setDeleting(p)}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-danger-500 hover:bg-danger-50"
                aria-label={t("common.delete")}
              >
                <Trash2 className="h-4 w-4" />
              </button>
              {p.connection === "bluetooth" && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => void handleRepair(p)}
                  isLoading={repairingId === p.id}
                  className="ml-auto"
                >
                  <Bluetooth className="h-4 w-4" />
                  {t("settings.printer.pairButton")}
                </Button>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => void handleTestPrint(p)}
                isLoading={testPrintingId === p.id}
                className={p.connection === "bluetooth" ? "" : "ml-auto"}
              >
                <Printer className="h-4 w-4" />
                {t("settings.printer.testPrint")}
              </Button>
            </div>
          </div>
        ))}
      </div>

      <PrinterProfileFormModal
        open={formOpen}
        onOpenChange={setFormOpen}
        profile={editing}
        onSubmit={handleSubmit}
        isSubmitting={isSubmitting}
      />

      <ConfirmModal
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={t("settings.printer.deleteConfirmTitle")}
        body={t("settings.printer.deleteConfirmBody", { name: deleting?.name })}
        isConfirming={isDeleting}
        onConfirm={() => void handleDelete()}
      />
    </div>
  );
}
