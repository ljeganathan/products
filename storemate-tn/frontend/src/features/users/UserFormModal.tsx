import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import type { StaffRole, UserCreate } from "@/types/user";

export interface UserFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: UserCreate) => Promise<void>;
  isSubmitting: boolean;
}

export function UserFormModal({ open, onOpenChange, onSubmit, isSubmitting }: UserFormModalProps) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<StaffRole>("pos_user");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName("");
    setEmail("");
    setPhone("");
    setPassword("");
    setRole("pos_user");
    setError(null);
  }, [open]);

  async function handleSubmit() {
    if (!name.trim() || !email.trim() || password.length < 8) {
      setError(t("users.formRequired"));
      return;
    }
    setError(null);
    await onSubmit({
      name: name.trim(),
      email: email.trim(),
      phone: phone.trim() || null,
      password,
      role,
    });
  }

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={t("users.addTitle")}
      footer={
        <Button onClick={() => void handleSubmit()} isLoading={isSubmitting}>
          {t("common.save")}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <Input label={t("users.name")} value={name} onChange={(e) => setName(e.target.value)} />
        <div className="grid grid-cols-2 gap-4">
          <Input
            label={t("users.email")}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
          <Input label={t("users.phone")} value={phone} onChange={(e) => setPhone(e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-4">
          <Input
            label={t("users.password")}
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            hint={t("users.passwordHint")}
          />
          <Select label={t("users.role")} value={role} onChange={(e) => setRole(e.target.value as StaffRole)}>
            <option value="admin">{t("roles.admin")}</option>
            <option value="pos_user">{t("roles.pos_user")}</option>
          </Select>
        </div>
        {error && <p className="text-sm text-danger-600">{error}</p>}
      </div>
    </Modal>
  );
}
