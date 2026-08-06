import { formatINR } from "@/lib/utils";
import type { PosItem } from "@/modules/pos/posApi";
import type { StockOverride } from "@/modules/pos/usePosWebSocket";

interface ItemCardProps {
  item: PosItem;
  resolvedPrice: number;
  quantityInCart: number;
  stockOverride?: StockOverride;
  onAdd: (item: PosItem) => void;
}

export function ItemCard({ item, resolvedPrice, quantityInCart, stockOverride, onAdd }: ItemCardProps) {
  const availableQty = stockOverride?.available_qty ?? item.available_qty;
  const isTracked = item.track_inventory;
  const isOutOfStock = isTracked && availableQty !== null && availableQty <= 0;
  const isLowStock = isTracked && !isOutOfStock && availableQty !== null && availableQty <= 5;
  const inCart = quantityInCart > 0;

  function handleActivate() {
    if (isOutOfStock) return;
    onAdd(item);
  }

  return (
    <button
      type="button"
      onClick={handleActivate}
      disabled={isOutOfStock}
      aria-disabled={isOutOfStock}
      className={`group relative flex min-h-[108px] flex-col gap-1.5 rounded-xl border p-2.5 text-left transition-all duration-100 ${
        item.is_combo_tile ? "col-span-2 min-h-[130px] justify-center gap-1 p-4" : ""
      } ${
        isOutOfStock
          ? "cursor-not-allowed border-border bg-surface-2 opacity-50"
          : item.is_combo_tile
            ? "border-[1.5px] border-gold bg-gradient-to-b from-gold-soft to-surface hover:-translate-y-0.5 hover:shadow-pos active:translate-y-0"
            : inCart
              ? "border-accent bg-surface hover:-translate-y-0.5 hover:shadow-pos active:translate-y-0"
              : "border-border bg-surface hover:-translate-y-0.5 hover:border-accent hover:shadow-pos active:translate-y-0"
      }`}
    >
      {isLowStock && (
        <span className="absolute right-2 top-2 rounded-full bg-chili-soft px-1.5 py-0.5 text-[9px] font-extrabold text-chili">
          {availableQty} left
        </span>
      )}
      {isOutOfStock && (
        <span className="absolute right-2 top-2 rounded-full bg-surface-3 px-1.5 py-0.5 text-[9px] font-extrabold text-ink-faint">
          Out of stock
        </span>
      )}

      <div className="flex items-start justify-between gap-1.5 pr-14">
        {item.is_combo_tile ? (
          <span className="rounded-full bg-gold-soft px-2 py-0.5 text-[10px] font-extrabold text-gold">
            🍱 Combo
          </span>
        ) : item.is_top_seller ? (
          <span className="text-[10px] font-bold text-gold">★ top seller</span>
        ) : (
          <span />
        )}
      </div>

      {item.image_url && (
        <img
          src={item.image_url}
          alt=""
          className={`w-full rounded-md object-cover ${item.is_combo_tile ? "h-24" : "h-14"}`}
        />
      )}

      <div className="leading-tight">
        <span className={`font-bold ${item.is_combo_tile ? "text-base" : "text-[13px]"}`}>
          {item.name_en}
        </span>
        {item.item_code && (
          <span className="ml-1 font-mono text-[10px] font-medium text-ink-faint">#{item.item_code}</span>
        )}
        {item.name_ta && <span className="ta block text-xs font-medium text-ink-soft">{item.name_ta}</span>}
      </div>

      <div className="mt-auto flex items-center justify-between gap-1.5">
        <span
          className={`tabular-nums font-extrabold ${item.is_combo_tile ? "text-[15px]" : "text-[13px]"}`}
        >
          {formatINR(resolvedPrice)}
        </span>
        {!isOutOfStock && (
          <span
            className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-extrabold transition-colors ${
              inCart
                ? "bg-accent text-accent-foreground"
                : "bg-accent-soft text-accent group-hover:bg-accent group-hover:text-accent-foreground"
            }`}
          >
            {inCart ? `Qty ${quantityInCart}` : "+ Add"}
          </span>
        )}
      </div>
    </button>
  );
}
