import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import type {
  PrinterConnection,
  PrinterProfile,
  PrinterProfileCreate,
  PrinterType,
} from "@/types/printer";

const DEFAULT_WIDTHS: Record<PrinterType, number> = {
  thermal_58mm: 32,
  thermal_80mm: 42,
  dot_matrix: 80,
};

export interface PrinterProfileFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  profile: PrinterProfile | null;
  onSubmit: (payload: PrinterProfileCreate) => Promise<void>;
  isSubmitting: boolean;
}

export function PrinterProfileFormModal({
  open,
  onOpenChange,
  profile,
  onSubmit,
  isSubmitting,
}: PrinterProfileFormModalProps) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [type, setType] = useState<PrinterType>("thermal_80mm");
  const [connection, setConnection] = useState<PrinterConnection>("local_agent");
  const [paperWidth, setPaperWidth] = useState(String(DEFAULT_WIDTHS.thermal_80mm));
  const [isDefault, setIsDefault] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(profile?.name ?? "");
    setType(profile?.type ?? "thermal_80mm");
    setConnection(profile?.connection ?? "local_agent");
    setPaperWidth(String(profile?.paper_width_chars ?? DEFAULT_WIDTHS.thermal_80mm));
    setIsDefault(profile?.is_default ?? false);
  }, [open, profile]);

  function handleTypeChange(nextType: PrinterType) {
    setType(nextType);
    if (!profile) setPaperWidth(String(DEFAULT_WIDTHS[nextType]));
    if (nextType === "dot_matrix") setConnection("local_agent");
  }

  async function handleSubmit() {
    await onSubmit({
      name: name.trim(),
      type,
      connection,
      paper_width_chars: Number(paperWidth) || DEFAULT_WIDTHS[type],
      is_default: isDefault,
    });
  }

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={profile ? t("settings.printer.editTitle") : t("settings.printer.addTitle")}
      footer={
        <Button onClick={() => void handleSubmit()} isLoading={isSubmitting}>
          {t("common.save")}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <Input label={t("settings.printer.name")} value={name} onChange={(e) => setName(e.target.value)} />
        <Select
          label={t("settings.printer.type")}
          value={type}
          onChange={(e) => handleTypeChange(e.target.value as PrinterType)}
        >
          <option value="thermal_58mm">{t("settings.printer.types.thermal_58mm")}</option>
          <option value="thermal_80mm">{t("settings.printer.types.thermal_80mm")}</option>
          <option value="dot_matrix">{t("settings.printer.types.dot_matrix")}</option>
        </Select>
        <Select
          label={t("settings.printer.connection")}
          value={connection}
          onChange={(e) => setConnection(e.target.value as PrinterConnection)}
          disabled={type === "dot_matrix"}
        >
          <option value="local_agent">{t("settings.printer.connections.local_agent")}</option>
          <option value="webusb">{t("settings.printer.connections.webusb")}</option>
        </Select>
        <Input
          type="number"
          min="1"
          label={t("settings.printer.paperWidth")}
          value={paperWidth}
          onChange={(e) => setPaperWidth(e.target.value)}
        />
        <label className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={isDefault}
            onChange={(e) => setIsDefault(e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          {t("settings.printer.setDefault")}
        </label>
      </div>
    </Modal>
  );
}
