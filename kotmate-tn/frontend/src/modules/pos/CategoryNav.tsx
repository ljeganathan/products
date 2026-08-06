import type { Category } from "@/modules/admin/categoriesApi";

export const TOP_SELLING_ID = "__top_selling__";

interface CategoryNavProps {
  categories: Category[];
  activeCategoryId: string;
  onSelect: (categoryId: string) => void;
  variant: "rail" | "strip";
}

export function CategoryNav({ categories, activeCategoryId, onSelect, variant }: CategoryNavProps) {
  const items = [{ id: TOP_SELLING_ID, name_en: "Top Selling", icon: "⭐" }, ...categories.map((c) => ({ ...c, icon: "🍽️" }))];

  if (variant === "rail") {
    return (
      <nav className="flex w-[92px] flex-none flex-col gap-1.5 overflow-y-auto border-r border-border bg-surface p-2">
        {items.map((c, index) => (
          <button
            key={c.id}
            type="button"
            onClick={() => onSelect(c.id)}
            className={`relative flex min-h-[64px] flex-col items-center justify-center gap-1 rounded-xl border px-1 py-2.5 transition-colors ${
              activeCategoryId === c.id
                ? "border-accent bg-accent-soft text-accent"
                : "border-transparent text-ink-soft hover:bg-surface-2"
            }`}
          >
            {index < 9 && (
              <span className="absolute right-1.5 top-1 text-[8.5px] font-extrabold text-ink-faint">
                F{index + 1}
              </span>
            )}
            <span className="text-lg leading-none">{c.icon}</span>
            <span className="text-center text-[10.5px] font-bold leading-tight">{c.name_en}</span>
          </button>
        ))}
      </nav>
    );
  }

  return (
    <nav className="flex gap-2 overflow-x-auto border-b border-border bg-surface px-3 py-2.5">
      {items.map((c) => (
        <button
          key={c.id}
          type="button"
          onClick={() => onSelect(c.id)}
          className={`flex shrink-0 items-center gap-1.5 rounded-full px-4 py-2 text-sm font-bold transition-colors ${
            activeCategoryId === c.id
              ? "bg-accent text-accent-foreground"
              : "border border-border bg-surface text-ink-soft"
          }`}
        >
          <span className="text-sm leading-none">{c.icon}</span>
          {c.name_en}
        </button>
      ))}
    </nav>
  );
}
