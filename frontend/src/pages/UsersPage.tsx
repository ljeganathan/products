import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { createUser, deleteUser, listUsers } from "@/api/users";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmModal } from "@/components/ui/ConfirmModal";
import { PageHeader } from "@/components/ui/PageHeader";
import { Table, type Column } from "@/components/ui/Table";
import { UserFormModal } from "@/features/users/UserFormModal";
import { useAuthStore } from "@/store/authStore";
import { toast } from "@/store/toastStore";
import type { User, UserCreate } from "@/types/user";
import { getApiErrorMessage } from "@/utils/apiError";

export default function UsersPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const currentUserId = useAuthStore((s) => s.user?.id);
  const currentStoreId = useAuthStore((s) => s.user?.store_id ?? undefined);

  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deleting, setDeleting] = useState<User | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["users", page, search],
    queryFn: () => listUsers({ page, page_size: 20, search: search || undefined }),
  });

  async function invalidate() {
    await queryClient.invalidateQueries({ queryKey: ["users"] });
  }

  async function handleCreate(payload: UserCreate) {
    setIsSubmitting(true);
    try {
      await createUser({ ...payload, store_id: currentStoreId ?? null });
      await invalidate();
      setFormOpen(false);
      toast("success", t("common.saved"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function confirmDelete() {
    if (!deleting) return;
    setIsDeleting(true);
    try {
      await deleteUser(deleting.id);
      await invalidate();
      setDeleting(null);
      toast("success", t("common.deleted"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsDeleting(false);
    }
  }

  const columns: Column<User>[] = [
    {
      key: "name",
      header: t("users.name"),
      render: (u) => (
        <div>
          <p className="font-medium text-slate-900">{u.name}</p>
          <p className="text-xs text-slate-500">{u.email}</p>
        </div>
      ),
    },
    { key: "role", header: t("users.role"), render: (u) => t(`roles.${u.role}`) },
    { key: "phone", header: t("users.phone"), render: (u) => u.phone ?? "—" },
    {
      key: "status",
      header: t("common.status"),
      render: (u) => (
        <Badge variant={u.is_active ? "success" : "danger"}>
          {u.is_active ? t("common.active") : t("common.inactive")}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: t("common.actions"),
      render: (u) => (
        <Button
          variant="ghost"
          size="sm"
          disabled={!u.is_active || u.id === currentUserId}
          onClick={() => setDeleting(u)}
        >
          {t("common.delete")}
        </Button>
      ),
    },
  ];

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={t("nav.users")}
        subtitle={t("users.subtitle")}
        actions={
          <Button onClick={() => setFormOpen(true)}>
            <Plus className="h-4 w-4" />
            {t("users.addButton")}
          </Button>
        }
      />

      <Table
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(u) => u.id}
        isLoading={isLoading}
        emptyMessage={t("users.empty")}
        search={search}
        onSearchChange={(v) => {
          setSearch(v);
          setPage(1);
        }}
        searchPlaceholder={t("users.searchPlaceholder")}
        page={page}
        pageSize={20}
        total={data?.total}
        onPageChange={setPage}
      />

      <UserFormModal
        open={formOpen}
        onOpenChange={setFormOpen}
        onSubmit={handleCreate}
        isSubmitting={isSubmitting}
      />

      <ConfirmModal
        open={deleting !== null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={t("users.deleteConfirmTitle")}
        body={t("users.deleteConfirmBody", { name: deleting?.name })}
        isConfirming={isDeleting}
        onConfirm={() => void confirmDelete()}
      />
    </div>
  );
}
