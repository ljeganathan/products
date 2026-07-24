import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { getLanguageSettings, updateLanguageSettings } from "@/api/languageSettings";
import { PageHeader } from "@/components/ui/PageHeader";
import { useAuthStore } from "@/store/authStore";
import { toast } from "@/store/toastStore";
import type { LanguagePref } from "@/types/auth";
import { cn } from "@/utils/cn";
import { getApiErrorMessage } from "@/utils/apiError";

const OPTIONS: { code: LanguagePref; labelKey: string }[] = [
  { code: "en", labelKey: "settings.language.english" },
  { code: "ta", labelKey: "settings.language.tamil" },
];

export default function LanguageSettingsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const setUser = useAuthStore((s) => s.setUser);
  const user = useAuthStore((s) => s.user);
  const [isSaving, setIsSaving] = useState<LanguagePref | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["language-settings"],
    queryFn: () => getLanguageSettings(),
  });

  async function handleSelect(code: LanguagePref) {
    setIsSaving(code);
    try {
      await updateLanguageSettings(code);
      await queryClient.invalidateQueries({ queryKey: ["language-settings"] });
      void i18n.changeLanguage(code);
      if (user) setUser({ ...user, language_pref: code });
      toast("success", t("common.saved"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsSaving(null);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("settings.language.title")} subtitle={t("settings.language.subtitle")} />

      {isLoading && <p className="text-slate-500">{t("common.loading")}</p>}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 sm:max-w-md">
        {OPTIONS.map((opt) => {
          const isSelected = data?.language_pref === opt.code;
          return (
            <button
              key={opt.code}
              type="button"
              onClick={() => void handleSelect(opt.code)}
              disabled={isSaving !== null}
              className={cn(
                "flex items-center justify-between rounded-xl border p-4 text-left",
                isSelected ? "border-brand-600 bg-brand-50" : "border-slate-200 bg-white hover:bg-slate-50",
              )}
            >
              <span className="font-medium text-slate-900">{t(opt.labelKey)}</span>
              {isSelected && <Check className="h-5 w-5 text-brand-600" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}
