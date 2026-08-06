import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { getMaintenanceSettings, updateMaintenanceSettings } from "@/modules/product-owner/platformApi";

export function MaintenancePage() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["maintenance-settings"],
    queryFn: getMaintenanceSettings,
  });

  const [maintenanceMode, setMaintenanceMode] = useState(false);
  const [maintenanceMessage, setMaintenanceMessage] = useState("");
  const [announcementActive, setAnnouncementActive] = useState(false);
  const [announcementMessage, setAnnouncementMessage] = useState("");

  useEffect(() => {
    if (!data) return;
    setMaintenanceMode(data.maintenance_mode);
    setMaintenanceMessage(data.maintenance_message ?? "");
    setAnnouncementActive(data.announcement_is_active);
    setAnnouncementMessage(data.announcement_message ?? "");
  }, [data]);

  const mutation = useMutation({
    mutationFn: () =>
      updateMaintenanceSettings({
        maintenance_mode: maintenanceMode,
        maintenance_message: maintenanceMessage || null,
        announcement_is_active: announcementActive,
        announcement_message: announcementMessage || null,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["maintenance-settings"] }),
  });

  if (isLoading) return <p className="text-sm text-foreground/60">Loading…</p>;

  return (
    <div className="max-w-xl">
      <h1 className="mb-4 text-xl font-bold">Maintenance</h1>

      <div className="flex flex-col gap-6">
        <div className="rounded-lg border border-border p-4">
          <label className="flex items-center gap-2 text-sm font-semibold">
            <input
              type="checkbox"
              checked={maintenanceMode}
              onChange={(e) => setMaintenanceMode(e.target.checked)}
            />
            Maintenance Mode
          </label>
          <p className="mt-1 text-xs text-foreground/60">
            When on, every login except Product Owner is blocked with the message below.
          </p>
          <textarea
            rows={3}
            placeholder="Down for scheduled maintenance, back by 10 PM."
            className="mt-3 w-full rounded-md border border-border bg-background p-2 text-sm"
            value={maintenanceMessage}
            onChange={(e) => setMaintenanceMessage(e.target.value)}
          />
        </div>

        <div className="rounded-lg border border-border p-4">
          <label className="flex items-center gap-2 text-sm font-semibold">
            <input
              type="checkbox"
              checked={announcementActive}
              onChange={(e) => setAnnouncementActive(e.target.checked)}
            />
            Announcement Banner
          </label>
          <p className="mt-1 text-xs text-foreground/60">
            Shown to every tenant as a dismissible banner — doesn't block login.
          </p>
          <textarea
            rows={3}
            placeholder="New: WhatsApp bill notifications coming soon!"
            className="mt-3 w-full rounded-md border border-border bg-background p-2 text-sm"
            value={announcementMessage}
            onChange={(e) => setAnnouncementMessage(e.target.value)}
          />
        </div>

        <button
          type="button"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate()}
          className="self-start rounded-md bg-accent px-5 py-2.5 text-sm font-semibold text-accent-foreground disabled:opacity-60"
        >
          {mutation.isPending ? "Saving…" : "Save Settings"}
        </button>
      </div>
    </div>
  );
}
