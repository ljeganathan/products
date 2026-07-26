import { Search } from "lucide-react";
import { forwardRef, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import type { ItemCatalog } from "@/features/pos/hooks/useItemCatalog";
import type { Item } from "@/types/item";
import { formatPaise } from "@/utils/money";
import { cn } from "@/utils/cn";

export interface ItemSearchBarProps {
  catalog: ItemCatalog;
  onSelect: (item: Item) => void;
}

// Shown when the cashier hits space on an empty search box to browse the
// whole catalog — capped so the dropdown stays scannable/scrollable rather
// than rendering a 1000-item list.
const SHOW_ALL_LIMIT = 50;

export const ItemSearchBar = forwardRef<HTMLInputElement, ItemSearchBarProps>(
  function ItemSearchBar({ catalog, onSelect }, ref) {
    const { t } = useTranslation();
    const [query, setQuery] = useState("");
    const [results, setResults] = useState<Item[]>([]);
    const [activeIndex, setActiveIndex] = useState(0);
    const [isOpen, setIsOpen] = useState(false);
    const [showingAll, setShowingAll] = useState(false);
    const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

    useEffect(() => {
      const trimmed = query.trim();
      if (!trimmed) {
        if (!showingAll) setResults([]);
        if (!showingAll) setIsOpen(false);
        return;
      }
      setShowingAll(false);

      const local = catalog.searchLocal(trimmed, 8);
      setResults(local);
      setActiveIndex(0);
      setIsOpen(true);

      if (local.length === 0 && !catalog.isCacheComplete) {
        let cancelled = false;
        const timer = setTimeout(() => {
          void catalog.searchServer(trimmed, 8).then((serverResults) => {
            if (!cancelled) setResults(serverResults);
          });
        }, 200);
        return () => {
          cancelled = true;
          clearTimeout(timer);
        };
      }
    }, [query, catalog, showingAll]);

    useEffect(() => {
      if (isOpen) itemRefs.current[activeIndex]?.scrollIntoView({ block: "nearest" });
    }, [activeIndex, isOpen]);

    function selectItem(item: Item) {
      onSelect(item);
      setQuery("");
      setResults([]);
      setIsOpen(false);
      setShowingAll(false);
    }

    function showAllItems() {
      const all = catalog.items.slice(0, SHOW_ALL_LIMIT);
      setResults(all);
      setActiveIndex(0);
      setIsOpen(all.length > 0);
      setShowingAll(true);
    }

    function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
      if (e.key === " " && query === "") {
        e.preventDefault();
        showAllItems();
        return;
      }
      if (!isOpen || results.length === 0) return;
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, results.length - 1));
      } else if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        selectItem(results[activeIndex]);
      } else if (e.key === "Escape") {
        setIsOpen(false);
        setShowingAll(false);
      }
    }

    return (
      <div className="relative w-full">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-400" />
          <input
            ref={ref}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => results.length > 0 && setIsOpen(true)}
            onBlur={() => setTimeout(() => setIsOpen(false), 150)}
            placeholder={t("pos.searchPlaceholder")}
            className="h-14 w-full rounded-xl border border-slate-300 bg-white pl-11 pr-4 text-lg text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/30"
          />
        </div>

        {isOpen && results.length > 0 && (
          <ul className="absolute z-20 mt-1 max-h-80 w-full overflow-y-auto rounded-xl border border-slate-200 bg-white shadow-card-hover">
            {results.map((item, i) => (
              <li key={item.id}>
                <button
                  ref={(el) => {
                    itemRefs.current[i] = el;
                  }}
                  type="button"
                  onMouseDown={(e) => e.preventDefault()}
                  onClick={() => selectItem(item)}
                  onMouseEnter={() => setActiveIndex(i)}
                  className={cn(
                    "flex w-full items-center justify-between gap-3 px-4 py-3 text-left",
                    i === activeIndex ? "bg-brand-50" : "hover:bg-slate-50",
                  )}
                >
                  <div>
                    <p className="font-medium text-slate-900">{item.name_en}</p>
                    <p className="text-sm text-slate-500">
                      {item.name_ta}
                      {item.sku ? ` · ${item.sku}` : ""}
                    </p>
                  </div>
                  <span className="shrink-0 font-medium text-slate-700">
                    {formatPaise(item.selling_price_paise)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  },
);
