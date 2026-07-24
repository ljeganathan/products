import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { getPlatformSettings, updatePlatformSettings } from "@/api/platformSettings";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/ui/PageHeader";
import { Textarea } from "@/components/ui/Textarea";
import { toast } from "@/store/toastStore";
import { getApiErrorMessage } from "@/utils/apiError";

export default function OwnerMaintenancePage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");
  const [isSaving, setIsSaving] = useState(false);

  const { data: settings, isLoading } = useQuery({
    queryKey: ["platform-settings"],
    queryFn: () => getPlatformSettings(),
  });

  useEffect(() => {
    if (settings) setMessage(settings.maintenance_message ?? "");
  }, [settings]);

  async function toggle(nextMode: boolean) {
    setIsSaving(true);
    try {
      await updatePlatformSettings({ maintenance_mode: nextMode, maintenance_message: message });
      await queryClient.invalidateQueries({ queryKey: ["platform-settings"] });
      toast("success", nextMode ? t("owner.maintenance.enabled") : t("owner.maintenance.disabled"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsSaving(false);
    }
  }

  if (isLoading) {
    return <p className="text-slate-500">{t("common.loading")}</p>;
  }

  const isOn = settings?.maintenance_mode ?? false;

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("owner.maintenance.title")} subtitle={t("owner.maintenance.subtitle")} />

      <div className="max-w-xl rounded-xl border border-slate-200 bg-white p-6 shadow-card">
        <div className="flex items-center justify-between">
          <div>
            <p className="font-medium text-slate-900">{t("owner.maintenance.statusLabel")}</p>
            <p className="text-sm text-slate-500">
              {isOn ? t("owner.maintenance.currentlyOn") : t("owner.maintenance.currentlyOff")}
            </p>
          </div>
          <Button
            variant={isOn ? "danger" : "primary"}
            isLoading={isSaving}
            onClick={() => void toggle(!isOn)}
          >
            {isOn ? t("owner.maintenance.turnOff") : t("owner.maintenance.turnOn")}
          </Button>
        </div>

        <div className="mt-6">
          <Textarea
            label={t("owner.maintenance.messageLabel")}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            placeholder={t("owner.maintenance.messagePlaceholder")}
          />
          <p className="mt-1.5 text-xs text-slate-500">{t("owner.maintenance.messageHint")}</p>
        </div>
      </div>
    </div>
  );
}
