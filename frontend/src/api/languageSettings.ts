import { apiClient } from "@/api/client";
import type { LanguagePref } from "@/types/auth";

export interface LanguageSettings {
  language_pref: LanguagePref;
}

export async function getLanguageSettings(): Promise<LanguageSettings> {
  const { data } = await apiClient.get<LanguageSettings>("/settings/language");
  return data;
}

export async function updateLanguageSettings(languagePref: LanguagePref): Promise<LanguageSettings> {
  const { data } = await apiClient.patch<LanguageSettings>("/settings/language", {
    language_pref: languagePref,
  });
  return data;
}
