import { api } from "@/lib/api";

export async function updateReportPrintingSetting(enabled: boolean): Promise<{ enabled: boolean }> {
  return (await api.patch<{ enabled: boolean }>("/api/v1/settings/report-printing", { enabled })).data;
}
