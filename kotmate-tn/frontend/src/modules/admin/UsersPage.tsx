import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { type FormEvent, useMemo, useState } from "react";

import { listLocations } from "@/modules/admin/locationsApi";
import {
  STAFF_ROLE_LABELS,
  type StaffRole,
  type TenantUser,
  type UserCreatePayload,
  createUser,
  getSeatUsage,
  listUsers,
  resetUserPassword,
  updateUser,
} from "@/modules/admin/usersApi";
import { me } from "@/modules/auth/authApi";
import { useAuthStore } from "@/modules/auth/authStore";

const inputClass =
  "min-h-10 rounded-md border border-border bg-background px-3 text-sm outline-none focus:ring-2 focus:ring-accent";
const labelClass = "text-xs font-medium text-foreground/70";

const STAFF_ROLES: StaffRole[] = ["tenant_admin", "pos_user", "waiter", "kitchen", "pos_operator"];
const BILLABLE_ROLES: StaffRole[] = ["tenant_admin", "pos_user", "pos_operator"];
const INCENTIVE_ROLES: StaffRole[] = ["pos_user", "pos_operator"];
// Both Pro Max only (production feedback round 2) — hidden from the role dropdown
// entirely rather than shown-then-rejected, same pattern as other plan-gated options
// elsewhere in Settings/Printers.
const PLAN_GATED_ROLES: Partial<Record<StaffRole, string>> = {
  kitchen: "kds",
  pos_operator: "pos_operator_role",
};

function apiErrorMessage(err: unknown, fallback: string): string {
  if (axios.isAxiosError(err) && err.response?.data?.detail) {
    return String(err.response.data.detail);
  }
  return fallback;
}

function RoleBadge({ role }: { role: StaffRole }) {
  const colors: Record<StaffRole, string> = {
    tenant_admin: "bg-chili/10 text-chili",
    pos_user: "bg-accent/15 text-accent-foreground",
    waiter: "bg-gold/15 text-gold",
    kitchen: "bg-foreground/10 text-foreground/70",
    pos_operator: "bg-veg/15 text-veg",
  };
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${colors[role] ?? "bg-foreground/10"}`}
    >
      {STAFF_ROLE_LABELS[role]}
    </span>
  );
}

interface UserFormState {
  local_handle: string;
  name: string;
  phone: string;
  role: StaffRole;
  password: string;
  incentive_rate: string;
  location_ids: string[];
}

const emptyForm: UserFormState = {
  local_handle: "",
  name: "",
  phone: "",
  role: "pos_user",
  password: "",
  incentive_rate: "",
  location_ids: [],
};

function UserFormModal({
  editingUser,
  tenantCode,
  locations,
  seatUsage,
  planFeatures,
  onClose,
}: {
  editingUser: TenantUser | null;
  tenantCode: string | null;
  locations: { id: string; name: string }[];
  seatUsage: { active_billable_users: number; max_users: number | null } | undefined;
  planFeatures: Record<string, boolean | string | string[] | undefined> | null | undefined;
  onClose: () => void;
}) {
  const visibleRoles = STAFF_ROLES.filter((role) => {
    const featureKey = PLAN_GATED_ROLES[role];
    // Editing an existing user of a role that's since become plan-gated-off still shows
    // it, so the dropdown doesn't silently drop the currently-selected value.
    return !featureKey || planFeatures?.[featureKey] === true || editingUser?.role === role;
  });
  const queryClient = useQueryClient();
  const [form, setForm] = useState<UserFormState>(
    editingUser
      ? {
          local_handle: editingUser.local_handle,
          name: editingUser.name,
          phone: editingUser.phone ?? "",
          role: editingUser.role,
          password: "",
          incentive_rate: editingUser.incentive_rate?.toString() ?? "",
          location_ids: editingUser.location_ids,
        }
      : emptyForm,
  );
  const [error, setError] = useState<string | null>(null);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["tenant-users"] });
    void queryClient.invalidateQueries({ queryKey: ["seat-usage"] });
  };

  const createMutation = useMutation({
    mutationFn: (payload: UserCreatePayload) => createUser(payload),
    onSuccess: () => {
      invalidate();
      onClose();
    },
    onError: (err) => setError(apiErrorMessage(err, "Failed to create user.")),
  });

  const updateMutation = useMutation({
    mutationFn: () =>
      updateUser(editingUser!.id, {
        name: form.name,
        phone: form.phone || undefined,
        role: form.role,
        incentive_rate:
          INCENTIVE_ROLES.includes(form.role) && form.incentive_rate ? Number(form.incentive_rate) : null,
        location_ids: form.location_ids,
      }),
    onSuccess: () => {
      invalidate();
      onClose();
    },
    onError: (err) => setError(apiErrorMessage(err, "Failed to update user.")),
  });

  function toggleLocation(id: string) {
    setForm((f) => ({
      ...f,
      location_ids: f.location_ids.includes(id)
        ? f.location_ids.filter((l) => l !== id)
        : [...f.location_ids, id],
    }));
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (editingUser) {
      updateMutation.mutate();
      return;
    }
    createMutation.mutate({
      local_handle: form.local_handle,
      name: form.name,
      phone: form.phone || undefined,
      role: form.role,
      password: form.password,
      incentive_rate:
        INCENTIVE_ROLES.includes(form.role) && form.incentive_rate ? Number(form.incentive_rate) : null,
      location_ids: form.location_ids,
    });
  }

  const isPending = createMutation.isPending || updateMutation.isPending;
  const seatCapReached =
    !editingUser &&
    BILLABLE_ROLES.includes(form.role) &&
    seatUsage?.max_users != null &&
    seatUsage.active_billable_users >= seatUsage.max_users;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-lg bg-background p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-bold">{editingUser ? "Edit User" : "Add User"}</h2>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Login Handle</label>
              <input
                required
                disabled={!!editingUser}
                placeholder="e.g. cashier01"
                pattern="[A-Za-z0-9_-]+"
                className={`${inputClass} disabled:opacity-60`}
                value={form.local_handle}
                onChange={(e) => setForm((f) => ({ ...f, local_handle: e.target.value }))}
              />
              {tenantCode && (
                <p className="text-[11px] text-foreground/50">
                  Login ID: {tenantCode}-{form.local_handle || "…"}
                </p>
              )}
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Name</label>
              <input
                required
                className={inputClass}
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Phone</label>
              <input
                className={inputClass}
                value={form.phone}
                onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Role</label>
              <select
                className={inputClass}
                value={form.role}
                onChange={(e) => setForm((f) => ({ ...f, role: e.target.value as StaffRole }))}
              >
                {visibleRoles.map((role) => (
                  <option key={role} value={role}>
                    {STAFF_ROLE_LABELS[role]}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {!editingUser && (
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Password</label>
              <input
                required
                minLength={8}
                type="password"
                className={inputClass}
                value={form.password}
                onChange={(e) => setForm((f) => ({ ...f, password: e.target.value }))}
              />
            </div>
          )}

          {INCENTIVE_ROLES.includes(form.role) && (
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Incentive Rate (% of net sale value)</label>
              <input
                type="number"
                min={0}
                max={100}
                step="0.1"
                className={inputClass}
                value={form.incentive_rate}
                onChange={(e) => setForm((f) => ({ ...f, incentive_rate: e.target.value }))}
              />
            </div>
          )}

          {locations.length > 0 && (
            <div className="flex flex-col gap-1.5">
              <label className={labelClass}>Location Access</label>
              <div className="flex flex-col gap-1.5 rounded-md border border-border p-2">
                {locations.map((loc) => (
                  <label key={loc.id} className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={form.location_ids.includes(loc.id)}
                      onChange={() => toggleLocation(loc.id)}
                    />
                    {loc.name}
                  </label>
                ))}
              </div>
            </div>
          )}

          {BILLABLE_ROLES.includes(form.role) && seatUsage && (
            <p className={`text-xs ${seatCapReached ? "text-chili" : "text-foreground/60"}`}>
              {seatUsage.active_billable_users} / {seatUsage.max_users ?? "∞"} POS seats used
              {seatCapReached && " — upgrade your plan to add more users."}
            </p>
          )}

          {error && (
            <p role="alert" className="rounded-md bg-chili/10 px-3 py-2 text-sm text-chili">
              {error}
            </p>
          )}

          <div className="mt-2 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-border px-4 py-2 text-sm font-semibold hover:bg-accent/10"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending || !!seatCapReached}
              className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-60"
            >
              {isPending ? "Saving…" : editingUser ? "Save Changes" : "Create User"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

function DeactivateDialog({ user, onClose }: { user: TenantUser; onClose: () => void }) {
  const queryClient = useQueryClient();
  const mutation = useMutation({
    mutationFn: () => updateUser(user.id, { is_active: !user.is_active }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["tenant-users"] });
      void queryClient.invalidateQueries({ queryKey: ["seat-usage"] });
      onClose();
    },
  });
  const activating = !user.is_active;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-lg bg-background p-6 shadow-xl">
        <h2 className="mb-2 text-lg font-bold">{activating ? "Reactivate" : "Deactivate"} User</h2>
        <p className="mb-4 text-sm text-foreground/70">
          {activating
            ? `${user.name} (${user.user_id}) will be able to log in again.`
            : `${user.name} (${user.user_id}) will no longer be able to log in. Their history on past bills and KOT tickets is preserved.`}
        </p>
        {mutation.isError && (
          <p className="mb-3 rounded-md bg-chili/10 px-3 py-2 text-sm text-chili">
            {apiErrorMessage(mutation.error, "Failed to update user.")}
          </p>
        )}
        <div className="flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-border px-4 py-2 text-sm font-semibold hover:bg-accent/10"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate()}
            className="rounded-md bg-chili px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
          >
            {mutation.isPending ? "Saving…" : activating ? "Reactivate" : "Deactivate"}
          </button>
        </div>
      </div>
    </div>
  );
}

function ResetPasswordDialog({ user, onClose }: { user: TenantUser; onClose: () => void }) {
  const [newPassword, setNewPassword] = useState("");
  const mutation = useMutation({
    mutationFn: () => resetUserPassword(user.id, newPassword),
    onSuccess: onClose,
  });

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="w-full max-w-sm rounded-lg bg-background p-6 shadow-xl">
        <h2 className="mb-2 text-lg font-bold">Reset Password</h2>
        <p className="mb-3 text-sm text-foreground/70">
          Set a new password for {user.name} ({user.user_id}).
        </p>
        <input
          required
          minLength={8}
          type="password"
          placeholder="New password"
          className={`${inputClass} w-full`}
          value={newPassword}
          onChange={(e) => setNewPassword(e.target.value)}
        />
        {mutation.isError && (
          <p className="mt-2 rounded-md bg-chili/10 px-3 py-2 text-sm text-chili">
            {apiErrorMessage(mutation.error, "Failed to reset password.")}
          </p>
        )}
        <div className="mt-4 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-border px-4 py-2 text-sm font-semibold hover:bg-accent/10"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={mutation.isPending || newPassword.length < 8}
            onClick={() => mutation.mutate()}
            className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground disabled:opacity-60"
          >
            {mutation.isPending ? "Saving…" : "Reset Password"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function UsersPage() {
  const loginId = useAuthStore((state) => state.loginId);
  const clearSession = useAuthStore((state) => state.clearSession);

  const { data: meData } = useQuery({ queryKey: ["me"], queryFn: me });
  const { data: users, isLoading, isError } = useQuery({ queryKey: ["tenant-users"], queryFn: listUsers });
  const { data: seatUsage } = useQuery({ queryKey: ["seat-usage"], queryFn: getSeatUsage });
  const { data: locations = [] } = useQuery({ queryKey: ["tenant-locations"], queryFn: listLocations });

  const [formUser, setFormUser] = useState<TenantUser | null | "new">(null);
  const [deactivateUser, setDeactivateUser] = useState<TenantUser | null>(null);
  const [resetPasswordUser, setResetPasswordUser] = useState<TenantUser | null>(null);

  const locationNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const loc of locations) map.set(loc.id, loc.name);
    return map;
  }, [locations]);

  return (
    <div className="min-h-screen w-full bg-background p-6 text-foreground">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="mt-1 text-xl font-bold">User Management</h1>
          <p className="text-sm text-foreground/60">
            {loginId} · Cashier / Waiter / KOT User accounts for this hotel
          </p>
        </div>
        <div className="flex items-center gap-3">
          {seatUsage && (
            <span className="rounded-full border border-border px-3 py-1.5 text-xs font-semibold">
              {seatUsage.active_billable_users} / {seatUsage.max_users ?? "∞"} POS seats used
            </span>
          )}
          <button
            type="button"
            onClick={() => setFormUser("new")}
            className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-accent-foreground"
          >
            + Add User
          </button>
          <button
            type="button"
            onClick={() => clearSession()}
            className="rounded-md border border-border px-3 py-2 text-xs font-semibold hover:bg-accent/10"
          >
            Log out
          </button>
        </div>
      </div>

      {isLoading && <p className="text-sm text-foreground/60">Loading…</p>}
      {isError && <p className="text-sm text-chili">Failed to load users.</p>}

      {users && (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-foreground/5 text-left text-xs uppercase tracking-wide text-foreground/60">
              <tr>
                <th className="px-4 py-2.5">Login ID</th>
                <th className="px-4 py-2.5">Name</th>
                <th className="px-4 py-2.5">Role</th>
                <th className="px-4 py-2.5">Status</th>
                <th className="px-4 py-2.5">Locations</th>
                <th className="px-4 py-2.5">Incentive</th>
                <th className="px-4 py-2.5">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.id} className="border-t border-border">
                  <td className="px-4 py-2.5 font-mono text-xs">{u.user_id}</td>
                  <td className="px-4 py-2.5">{u.name}</td>
                  <td className="px-4 py-2.5">
                    <RoleBadge role={u.role} />
                  </td>
                  <td className="px-4 py-2.5">
                    <span
                      className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                        u.is_active ? "bg-accent/15 text-accent-foreground" : "bg-foreground/10 text-foreground/50"
                      }`}
                    >
                      {u.is_active ? "Active" : "Deactivated"}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-foreground/70">
                    {u.location_ids.length === 0
                      ? "—"
                      : u.location_ids.map((id) => locationNameById.get(id) ?? id).join(", ")}
                  </td>
                  <td className="px-4 py-2.5 text-xs">
                    {INCENTIVE_ROLES.includes(u.role) && u.incentive_rate != null ? `${u.incentive_rate}%` : "—"}
                  </td>
                  <td className="px-4 py-2.5">
                    <div className="flex gap-3 text-xs font-semibold">
                      <button type="button" onClick={() => setFormUser(u)} className="text-accent hover:underline">
                        Edit
                      </button>
                      <button
                        type="button"
                        onClick={() => setResetPasswordUser(u)}
                        className="text-accent hover:underline"
                      >
                        Reset Password
                      </button>
                      <button
                        type="button"
                        onClick={() => setDeactivateUser(u)}
                        className={u.is_active ? "text-chili hover:underline" : "text-accent hover:underline"}
                      >
                        {u.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {formUser && (
        <UserFormModal
          editingUser={formUser === "new" ? null : formUser}
          tenantCode={meData?.tenant_code ?? null}
          locations={locations}
          seatUsage={seatUsage}
          planFeatures={meData?.features}
          onClose={() => setFormUser(null)}
        />
      )}
      {deactivateUser && (
        <DeactivateDialog user={deactivateUser} onClose={() => setDeactivateUser(null)} />
      )}
      {resetPasswordUser && (
        <ResetPasswordDialog user={resetPasswordUser} onClose={() => setResetPasswordUser(null)} />
      )}
    </div>
  );
}
