import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Pencil } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { listTenantUsers, updateTenantUser } from "@/api/platformUsers";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { toast } from "@/store/toastStore";
import type { PlatformUserUpdate, User } from "@/types/user";
import { getApiErrorMessage } from "@/utils/apiError";

export interface TenantUsersModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  tenantId: string;
  tenantName: string;
}

export function TenantUsersModal({ open, onOpenChange, tenantId, tenantName }: TenantUsersModalProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<{ name: string; email: string; phone: string; is_active: boolean }>({
    name: "",
    email: "",
    phone: "",
    is_active: true,
  });
  const [isSaving, setIsSaving] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["platform-tenant-users", tenantId],
    queryFn: () => listTenantUsers(tenantId),
    enabled: open,
  });

  function startEdit(user: User) {
    setEditingId(user.id);
    setDraft({
      name: user.name,
      email: user.email,
      phone: user.phone ?? "",
      is_active: user.is_active,
    });
  }

  async function saveEdit(user: User) {
    setIsSaving(true);
    const payload: PlatformUserUpdate = {
      name: draft.name.trim(),
      email: draft.email.trim(),
      phone: draft.phone.trim() || null,
      is_active: draft.is_active,
    };
    try {
      await updateTenantUser(tenantId, user.id, payload);
      await queryClient.invalidateQueries({ queryKey: ["platform-tenant-users", tenantId] });
      setEditingId(null);
      toast("success", t("common.saved"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onOpenChange={(next) => {
        if (!next) setEditingId(null);
        onOpenChange(next);
      }}
      title={t("owner.tenants.usersTitle", { name: tenantName })}
      className="max-w-2xl"
    >
      <div className="flex flex-col gap-3">
        {isLoading && <p className="text-sm text-slate-500">{t("common.loading")}</p>}
        {!isLoading && (data?.items.length ?? 0) === 0 && (
          <p className="text-sm text-slate-500">{t("users.empty")}</p>
        )}
        {data?.items.map((user) => {
          const isEditing = editingId === user.id;
          return (
            <div key={user.id} className="rounded-lg border border-slate-200 p-3">
              {isEditing ? (
                <div className="flex flex-col gap-3">
                  <div className="grid grid-cols-2 gap-3">
                    <Input
                      label={t("users.name")}
                      value={draft.name}
                      onChange={(e) => setDraft((d) => ({ ...d, name: e.target.value }))}
                    />
                    <Input
                      label={t("users.email")}
                      type="email"
                      value={draft.email}
                      onChange={(e) => setDraft((d) => ({ ...d, email: e.target.value }))}
                    />
                  </div>
                  <div className="grid grid-cols-2 items-end gap-3">
                    <Input
                      label={t("users.phone")}
                      value={draft.phone}
                      onChange={(e) => setDraft((d) => ({ ...d, phone: e.target.value }))}
                    />
                    <label className="mb-1.5 flex h-11 items-center gap-2 text-sm font-medium text-slate-700">
                      <input
                        type="checkbox"
                        checked={draft.is_active}
                        onChange={(e) => setDraft((d) => ({ ...d, is_active: e.target.checked }))}
                        className="h-4 w-4 rounded border-slate-300"
                      />
                      {t("common.active")}
                    </label>
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button variant="ghost" size="sm" onClick={() => setEditingId(null)}>
                      {t("common.cancel")}
                    </Button>
                    <Button size="sm" onClick={() => void saveEdit(user)} isLoading={isSaving}>
                      {t("common.save")}
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="flex items-center justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <p className="truncate font-medium text-slate-900">{user.name}</p>
                      <Badge variant="neutral">{t(`roles.${user.role}`)}</Badge>
                      <Badge variant={user.is_active ? "success" : "danger"}>
                        {user.is_active ? t("common.active") : t("common.inactive")}
                      </Badge>
                    </div>
                    <p className="truncate text-sm text-slate-500">
                      {user.email}
                      {user.phone ? ` · ${user.phone}` : ""}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => startEdit(user)}
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-slate-500 hover:bg-slate-100"
                    aria-label={t("common.edit")}
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </Modal>
  );
}
