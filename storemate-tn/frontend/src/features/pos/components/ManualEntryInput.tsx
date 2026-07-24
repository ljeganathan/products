import { ScanLine } from "lucide-react";
import { forwardRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { listItems } from "@/api/items";
import type { ItemCatalog } from "@/features/pos/hooks/useItemCatalog";
import { toast } from "@/store/toastStore";
import type { Item } from "@/types/item";

export interface ManualEntryInputProps {
  catalog: ItemCatalog;
  onFound: (item: Item) => void;
}

/** The visible manual-entry path (F3) — an exact barcode/SKU lookup
 * submitted with Enter. Distinct from the barcode-scanner hook, which
 * captures scan-speed keystrokes with no field focused. */
export const ManualEntryInput = forwardRef<HTMLInputElement, ManualEntryInputProps>(
  function ManualEntryInput({ catalog, onFound }, ref) {
    const { t } = useTranslation();
    const [code, setCode] = useState("");
    const [isSearching, setIsSearching] = useState(false);

    async function submit() {
      const trimmed = code.trim();
      if (!trimmed) return;

      const local = catalog.items.find((i) => i.barcode === trimmed || i.sku === trimmed);
      if (local) {
        onFound(local);
        setCode("");
        return;
      }

      setIsSearching(true);
      try {
        const resp = await listItems({ barcode: trimmed });
        if (resp.items.length > 0) {
          onFound(resp.items[0]);
          setCode("");
          return;
        }
        toast("danger", t("pos.itemNotFoundTitle"), t("pos.itemNotFoundDescription", { code: trimmed }));
      } finally {
        setIsSearching(false);
      }
    }

    return (
      <div className="relative">
        <ScanLine className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
        <input
          ref={ref}
          type="text"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              void submit();
            }
          }}
          placeholder={t("pos.manualEntryPlaceholder")}
          disabled={isSearching}
          className="h-14 w-full rounded-xl border border-slate-300 bg-white pl-11 pr-4 text-lg text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30 disabled:bg-slate-50"
        />
      </div>
    );
  },
);
