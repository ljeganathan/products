import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { resolveMediaUrl } from "@/api/client";
import { listPrinterProfiles } from "@/api/printerProfiles";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { dispatchPrint } from "@/features/pos/printDispatch";
import { toast } from "@/store/toastStore";
import type { BillPrintPayload } from "@/types/bill";
import { buildReceiptLines } from "@/utils/receiptLayout";

export interface PrintPreviewModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  payload: BillPrintPayload | null;
}

export function PrintPreviewModal({ open, onOpenChange, payload }: PrintPreviewModalProps) {
  const { t } = useTranslation();
  const { data: profiles } = useQuery({
    queryKey: ["printer-profiles"],
    queryFn: () => listPrinterProfiles(),
    enabled: open,
  });
  const [selectedProfileId, setSelectedProfileId] = useState<string | null>(null);
  const [isPrinting, setIsPrinting] = useState(false);
  const printButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!profiles || profiles.length === 0) return;
    if (selectedProfileId && profiles.some((p) => p.id === selectedProfileId)) return;
    setSelectedProfileId(profiles.find((p) => p.is_default)?.id ?? profiles[0].id);
  }, [profiles, selectedProfileId]);

  const selectedProfile = profiles?.find((p) => p.id === selectedProfileId) ?? null;
  const previewLines =
    payload && selectedProfile ? buildReceiptLines(payload, selectedProfile.paper_width_chars) : [];

  useEffect(() => {
    // The Print button starts disabled (profiles load async), so Radix's
    // one-time mount focus can land on it while it's still disabled and
    // silently no-op — re-focus once it actually becomes actionable so
    // Enter reliably prints without a second keypress.
    if (open && selectedProfile) printButtonRef.current?.focus();
  }, [open, selectedProfile]);

  async function handlePrint() {
    if (!payload || !selectedProfile) return;
    setIsPrinting(true);
    try {
      await dispatchPrint(selectedProfile, payload);
      toast("success", t("pos.printSuccessTitle"));
    } catch (err) {
      toast(
        "danger",
        t("pos.printFailedTitle"),
        err instanceof Error ? err.message : undefined,
      );
    } finally {
      setIsPrinting(false);
    }
  }

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={t("pos.printPreviewTitle")}
      className="max-w-2xl"
      initialFocusRef={printButtonRef}
      footer={
        <Button
          ref={printButtonRef}
          onClick={() => void handlePrint()}
          isLoading={isPrinting}
          disabled={!selectedProfile}
        >
          {t("pos.print")}
        </Button>
      }
    >
      {profiles && profiles.length > 1 && (
        <div className="mb-3 flex flex-wrap gap-2">
          {profiles.map((p) => (
            <button
              key={p.id}
              type="button"
              onClick={() => setSelectedProfileId(p.id)}
              className={`h-9 rounded-lg border px-3 text-sm font-medium ${
                selectedProfileId === p.id
                  ? "border-brand-600 bg-brand-600 text-white"
                  : "border-slate-300 text-slate-700"
              }`}
            >
              {p.name}
            </button>
          ))}
        </div>
      )}

      {!profiles?.length && (
        <p className="text-sm text-slate-500">{t("pos.noPrinterProfiles")}</p>
      )}

      {payload && selectedProfile && (
        // overflow-x-auto + whitespace-pre (not pre-wrap): a receipt line
        // reflowing inside a narrower modal than its true paper width would
        // misrepresent what actually prints — this scrolls instead so
        // every line stays exactly as wide as the real output.
        <div className="overflow-x-auto rounded-lg border border-slate-200 bg-slate-50 p-4">
          {payload.company.logo_url && (
            <img
              src={resolveMediaUrl(payload.company.logo_url)}
              alt={payload.company.display_name}
              className="mx-auto mb-2 h-16 object-contain"
            />
          )}
          <pre className="whitespace-pre font-mono text-xs leading-relaxed text-slate-800">
            {previewLines.join("\n")}
          </pre>
        </div>
      )}
    </Modal>
  );
}
