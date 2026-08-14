import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { toast } from "@/store/toastStore";
import type {
  PrinterConnection,
  PrinterConnectionDetails,
  PrinterProfile,
  PrinterProfileCreate,
  PrinterType,
} from "@/types/printer";
import { isWebBluetoothSupported, pairBluetoothPrinter } from "@/utils/webBluetoothPrinter";

// 12 dots/char at standard 203dpi Font A: 58mm -> 384 dots / 32 cols,
// 80mm -> 576 dots / 48 cols (matches paperWidthDots in printDispatch.ts
// and the equivalent preset in KOTMate TN's printing/base.py). A narrower
// value here under-uses the printer's actual width, leaving unused blank
// space down the right edge of every text line on real 80mm hardware.
const DEFAULT_WIDTHS: Record<PrinterType, number> = {
  thermal_58mm: 32,
  thermal_80mm: 48,
  dot_matrix: 80,
};

// Dot-matrix has no BLE/USB/RawBT path worth building for legacy hardware —
// only a driver-attached agent or a network print-server front it.
const CONNECTIONS_BY_TYPE: Record<PrinterType, PrinterConnection[]> = {
  thermal_58mm: ["local_agent", "webusb", "network", "wifi", "bluetooth", "rawbt"],
  thermal_80mm: ["local_agent", "webusb", "network", "wifi", "bluetooth", "rawbt"],
  dot_matrix: ["local_agent", "network"],
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
  const [connectionDetails, setConnectionDetails] = useState<PrinterConnectionDetails>({});
  const [isPairing, setIsPairing] = useState(false);

  useEffect(() => {
    if (!open) return;
    setName(profile?.name ?? "");
    setType(profile?.type ?? "thermal_80mm");
    setConnection(profile?.connection ?? "local_agent");
    setPaperWidth(String(profile?.paper_width_chars ?? DEFAULT_WIDTHS.thermal_80mm));
    setIsDefault(profile?.is_default ?? false);
    setConnectionDetails(profile?.connection_details ?? {});
  }, [open, profile]);

  function handleTypeChange(nextType: PrinterType) {
    setType(nextType);
    if (!profile) setPaperWidth(String(DEFAULT_WIDTHS[nextType]));
    if (!CONNECTIONS_BY_TYPE[nextType].includes(connection)) setConnection("local_agent");
  }

  function handleConnectionChange(next: PrinterConnection) {
    setConnection(next);
    setConnectionDetails({});
  }

  function setDetail(key: string, value: string) {
    setConnectionDetails((prev) => ({ ...prev, [key]: value }));
  }

  async function handlePair() {
    setIsPairing(true);
    try {
      const paired = await pairBluetoothPrinter();
      setConnectionDetails({
        bluetooth_device_id: paired.bluetooth_device_id,
        bluetooth_device_name: paired.bluetooth_device_name,
      });
      toast("success", t("settings.printer.pairSuccess", { name: paired.bluetooth_device_name }));
    } catch (err) {
      toast("danger", err instanceof Error ? err.message : t("settings.printer.pairError"));
    } finally {
      setIsPairing(false);
    }
  }

  async function handleSubmit() {
    await onSubmit({
      name: name.trim(),
      type,
      connection,
      paper_width_chars: Number(paperWidth) || DEFAULT_WIDTHS[type],
      is_default: isDefault,
      connection_details: connectionDetails,
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
          onChange={(e) => handleConnectionChange(e.target.value as PrinterConnection)}
        >
          {CONNECTIONS_BY_TYPE[type].map((c) => (
            <option key={c} value={c}>
              {t(`settings.printer.connections.${c}`)}
            </option>
          ))}
        </Select>

        {connection === "local_agent" && (
          <Input
            label={t("settings.printer.windowsPrinterName")}
            placeholder="POS80 Printer"
            hint={t("settings.printer.windowsPrinterNameHint")}
            value={connectionDetails.windows_printer_name ?? ""}
            onChange={(e) => setDetail("windows_printer_name", e.target.value)}
          />
        )}

        {(connection === "network" || connection === "wifi") && (
          <div className="grid grid-cols-2 gap-3">
            <Input
              label={t("settings.printer.ipAddress")}
              placeholder="192.168.1.50"
              value={connectionDetails.ip ?? ""}
              onChange={(e) => setDetail("ip", e.target.value)}
            />
            <Input
              label={t("settings.printer.port")}
              placeholder="9100"
              inputMode="numeric"
              value={connectionDetails.port ?? ""}
              onChange={(e) => setDetail("port", e.target.value.replace(/\D/g, ""))}
            />
          </div>
        )}

        {connection === "bluetooth" && (
          <div className="flex flex-col gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3">
            {connectionDetails.bluetooth_device_name ? (
              <p className="text-sm text-slate-700">
                {t("settings.printer.pairedWith")}{" "}
                <span className="font-medium">{connectionDetails.bluetooth_device_name}</span>
              </p>
            ) : (
              <p className="text-sm text-slate-500">{t("settings.printer.notPaired")}</p>
            )}
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="w-fit"
              onClick={() => void handlePair()}
              isLoading={isPairing}
              disabled={!isWebBluetoothSupported()}
            >
              {t("settings.printer.pairButton")}
            </Button>
            {!isWebBluetoothSupported() && (
              <p className="text-xs text-danger-600">{t("settings.printer.bluetoothUnsupported")}</p>
            )}
          </div>
        )}

        {connection === "rawbt" && (
          <p className="rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
            {t("settings.printer.rawbtHint")}
          </p>
        )}

        <Input
          type="number"
          min="1"
          label={t("settings.printer.paperWidth")}
          value={paperWidth}
          onChange={(e) => setPaperWidth(e.target.value)}
          hint={
            type !== "dot_matrix"
              ? t("settings.printer.paperWidthHint", { chars: DEFAULT_WIDTHS[type] })
              : undefined
          }
          error={
            // Typing the paper's mm size (e.g. "80") instead of its character
            // count is an easy mistake this field's own label doesn't fully
            // prevent — a value this far over the printer's actual native
            // width makes every centered/padded line hardware-wrap onto
            // extra, mostly-blank rows (exactly the "lot of spaces" symptom).
            type !== "dot_matrix" && Number(paperWidth) > DEFAULT_WIDTHS[type] * 1.25
              ? t("settings.printer.paperWidthWarning", { chars: DEFAULT_WIDTHS[type] })
              : undefined
          }
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
