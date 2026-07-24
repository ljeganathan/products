import { Upload } from "lucide-react";
import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { bulkImportItems } from "@/api/items";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";
import { toast } from "@/store/toastStore";
import type { BulkImportResult } from "@/types/item";
import { getApiErrorMessage } from "@/utils/apiError";

const TEMPLATE_COLUMNS = [
  "name_en", "name_ta", "category", "brand", "pack_size", "barcode", "sku", "unit",
  "mrp", "selling_price", "cost_price", "tax_profile", "hsn_code",
  "reorder_level", "reorder_qty", "opening_stock",
];

export interface BulkImportModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onImported: () => void;
}

export function BulkImportModal({ open, onOpenChange, onImported }: BulkImportModalProps) {
  const { t } = useTranslation();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isImporting, setIsImporting] = useState(false);
  const [result, setResult] = useState<BulkImportResult | null>(null);

  function handleClose(nextOpen: boolean) {
    if (!nextOpen) {
      setSelectedFile(null);
      setResult(null);
    }
    onOpenChange(nextOpen);
  }

  async function handleImport() {
    if (!selectedFile) return;
    setIsImporting(true);
    try {
      const importResult = await bulkImportItems(selectedFile);
      setResult(importResult);
      if (importResult.created_count > 0) onImported();
      if (importResult.error_count === 0) {
        toast("success", t("items.bulkImportSuccess", { count: importResult.created_count }));
      }
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("items.bulkImportError")));
    } finally {
      setIsImporting(false);
    }
  }

  return (
    <Modal
      open={open}
      onOpenChange={handleClose}
      title={t("items.bulkImportTitle")}
      description={t("items.bulkImportDescription")}
      className="max-w-xl"
      footer={
        !result && (
          <Button onClick={() => void handleImport()} isLoading={isImporting} disabled={!selectedFile}>
            {t("items.importButton")}
          </Button>
        )
      }
    >
      {!result && (
        <div className="flex flex-col gap-4">
          <p className="text-sm text-slate-500">
            {t("items.bulkImportColumns")}: {TEMPLATE_COLUMNS.join(", ")}
          </p>
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv,text/csv"
            onChange={(e) => setSelectedFile(e.target.files?.[0] ?? null)}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="flex h-32 flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-slate-300 text-slate-500 hover:border-brand-400 hover:text-brand-600"
          >
            <Upload className="h-6 w-6" />
            {selectedFile ? selectedFile.name : t("items.chooseFile")}
          </button>
        </div>
      )}

      {result && (
        <div className="flex flex-col gap-4">
          <div className="flex gap-4 text-sm">
            <span className="text-slate-600">
              {t("items.bulkImportTotalRows")}: <strong>{result.total_rows}</strong>
            </span>
            <span className="text-success-600">
              {t("items.bulkImportCreated")}: <strong>{result.created_count}</strong>
            </span>
            <span className="text-danger-600">
              {t("items.bulkImportErrors")}: <strong>{result.error_count}</strong>
            </span>
          </div>

          {result.errors.length > 0 && (
            <div className="max-h-64 overflow-y-auto rounded-lg border border-slate-200">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-3 py-2 font-medium text-slate-600">
                      {t("items.rowNumber")}
                    </th>
                    <th className="px-3 py-2 font-medium text-slate-600">
                      {t("items.rowErrors")}
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {result.errors.map((rowError) => (
                    <tr key={rowError.row_number}>
                      <td className="px-3 py-2 align-top text-slate-700">{rowError.row_number}</td>
                      <td className="px-3 py-2 text-danger-700">
                        <ul className="list-inside list-disc">
                          {rowError.errors.map((msg, i) => (
                            <li key={i}>{msg}</li>
                          ))}
                        </ul>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <Button variant="outline" onClick={() => setResult(null)}>
            {t("items.importAnother")}
          </Button>
        </div>
      )}
    </Modal>
  );
}
