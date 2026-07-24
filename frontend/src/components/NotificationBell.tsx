import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import { listNotifications, markNotificationRead } from "@/api/notifications";
import type { Notification } from "@/types/notification";
import { cn } from "@/utils/cn";

export function NotificationBell() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const { data: unread } = useQuery({
    queryKey: ["notifications-unread"],
    queryFn: () => listNotifications({ is_read: false, page_size: 1 }),
    refetchInterval: 60_000,
  });
  const { data: recent } = useQuery({
    queryKey: ["notifications-recent"],
    queryFn: () => listNotifications({ page_size: 10 }),
    enabled: isOpen,
  });

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  async function handleClick(notification: Notification) {
    if (!notification.is_read) {
      await markNotificationRead(notification.id);
      await queryClient.invalidateQueries({ queryKey: ["notifications-unread"] });
      await queryClient.invalidateQueries({ queryKey: ["notifications-recent"] });
    }
    // reference_id on a low_stock notification is the item that triggered
    // it — there's no per-item deep link in the stock UI yet, so the
    // low-stock list is the practical click-through target.
    if (notification.type === "low_stock") {
      setIsOpen(false);
      navigate("/stock/low-stock");
    }
  }

  const unreadCount = unread?.total ?? 0;

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setIsOpen((v) => !v)}
        className="relative flex h-11 w-11 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
        aria-label={t("notifications.title")}
      >
        <Bell className="h-5 w-5" />
        {unreadCount > 0 && (
          <span className="absolute right-1.5 top-1.5 flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-danger-600 px-1 text-[10px] font-semibold text-white">
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className="absolute right-0 z-40 mt-2 w-80 rounded-xl border border-slate-200 bg-white shadow-card-hover">
          <div className="border-b border-slate-100 px-4 py-3 font-medium text-slate-800">
            {t("notifications.title")}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {(recent?.items.length ?? 0) === 0 && (
              <p className="px-4 py-6 text-center text-sm text-slate-400">
                {t("notifications.empty")}
              </p>
            )}
            {recent?.items.map((n) => (
              <button
                key={n.id}
                type="button"
                onClick={() => void handleClick(n)}
                className={cn(
                  "block w-full border-b border-slate-50 px-4 py-3 text-left last:border-0 hover:bg-slate-50",
                  !n.is_read && "bg-brand-50/50",
                )}
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="text-sm font-medium text-slate-800">{n.title}</p>
                  {!n.is_read && <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-brand-600" />}
                </div>
                <p className="mt-0.5 text-sm text-slate-500">{n.body}</p>
                <p className="mt-1 text-xs text-slate-400">
                  {new Date(n.created_at).toLocaleString("en-IN")}
                </p>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
