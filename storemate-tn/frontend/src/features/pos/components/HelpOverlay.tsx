import { useTranslation } from "react-i18next";

import { Modal } from "@/components/ui/Modal";

export interface HelpOverlayProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const SHORTCUTS: { keys: string; labelKey: string }[] = [
  { keys: "F1", labelKey: "pos.shortcuts.help" },
  { keys: "F2", labelKey: "pos.shortcuts.focusSearch" },
  { keys: "F3", labelKey: "pos.shortcuts.focusManualEntry" },
  { keys: "F4", labelKey: "pos.shortcuts.billDiscount" },
  { keys: "F5", labelKey: "pos.shortcuts.itemDiscount" },
  { keys: "+ / -", labelKey: "pos.shortcuts.adjustQty" },
  { keys: "Ctrl + ↑ / ↓", labelKey: "pos.shortcuts.adjustQty" },
  { keys: "Delete", labelKey: "pos.shortcuts.removeLine" },
  { keys: "Ctrl + Z", labelKey: "pos.shortcuts.undo" },
  { keys: "F8", labelKey: "pos.shortcuts.hold" },
  { keys: "F9", labelKey: "pos.shortcuts.recall" },
  { keys: "F10 / Ctrl + Enter", labelKey: "pos.shortcuts.finalize" },
  { keys: "Esc", labelKey: "pos.shortcuts.cancel" },
];

/** Every shortcut listed here also has a visible on-screen button
 * equivalent elsewhere in the POS screen — this overlay is a reference,
 * not the only way to perform any of these actions. */
export function HelpOverlay({ open, onOpenChange }: HelpOverlayProps) {
  const { t } = useTranslation();

  return (
    <Modal open={open} onOpenChange={onOpenChange} title={t("pos.helpTitle")} description={t("pos.helpDescription")}>
      <ul className="divide-y divide-slate-100">
        {SHORTCUTS.map((s) => (
          <li key={s.labelKey + s.keys} className="flex items-center justify-between py-2">
            <span className="text-slate-700">{t(s.labelKey)}</span>
            <kbd className="rounded-md border border-slate-300 bg-slate-50 px-2 py-1 font-mono text-xs text-slate-600">
              {s.keys}
            </kbd>
          </li>
        ))}
      </ul>
    </Modal>
  );
}
