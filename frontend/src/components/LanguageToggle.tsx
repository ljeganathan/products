import { useTranslation } from "react-i18next";

import { cn } from "@/utils/cn";

const LANGUAGES: { code: "en" | "ta"; label: string }[] = [
  { code: "en", label: "EN" },
  { code: "ta", label: "த" },
];

export function LanguageToggle() {
  const { i18n, t } = useTranslation();
  const current = i18n.resolvedLanguage ?? i18n.language;

  return (
    <div
      role="group"
      aria-label={t("common.language")}
      className="flex h-11 items-center rounded-lg border border-slate-300 bg-white p-1"
    >
      {LANGUAGES.map(({ code, label }) => (
        <button
          key={code}
          type="button"
          onClick={() => void i18n.changeLanguage(code)}
          aria-pressed={current === code}
          className={cn(
            "flex h-9 min-w-[2.75rem] items-center justify-center rounded-md px-2 text-sm font-medium transition-colors",
            current === code ? "bg-brand-600 text-white" : "text-slate-600 hover:bg-slate-100",
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
