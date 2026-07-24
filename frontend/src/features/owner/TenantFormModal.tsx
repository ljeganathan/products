import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import type { PlanCode } from "@/types/plan";
import type { TenantCreate } from "@/types/tenant";

export interface TenantFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (payload: TenantCreate) => Promise<void>;
  isSubmitting: boolean;
}

export function TenantFormModal({ open, onOpenChange, onSubmit, isSubmitting }: TenantFormModalProps) {
  const { t } = useTranslation();
  const [name, setName] = useState("");
  const [ownerEmail, setOwnerEmail] = useState("");
  const [ownerPhone, setOwnerPhone] = useState("");
  const [planCode, setPlanCode] = useState<PlanCode>("lite");
  const [storeName, setStoreName] = useState("");
  const [adminName, setAdminName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setName("");
    setOwnerEmail("");
    setOwnerPhone("");
    setPlanCode("lite");
    setStoreName("");
    setAdminName("");
    setAdminEmail("");
    setAdminPassword("");
    setError(null);
  }, [open]);

  async function handleSubmit() {
    if (!name.trim() || !ownerEmail.trim() || !ownerPhone.trim()) {
      setError(t("owner.tenants.storeDetailsRequired"));
      return;
    }
    if (!adminName.trim() || !adminEmail.trim() || adminPassword.length < 8) {
      setError(t("owner.tenants.adminDetailsRequired"));
      return;
    }
    await onSubmit({
      name: name.trim(),
      owner_email: ownerEmail.trim(),
      owner_phone: ownerPhone.trim(),
      plan_code: planCode,
      store_name: storeName.trim() || null,
      admin_name: adminName.trim(),
      admin_email: adminEmail.trim(),
      admin_password: adminPassword,
    });
  }

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={t("owner.tenants.addTitle")}
      footer={
        <Button onClick={() => void handleSubmit()} isLoading={isSubmitting}>
          {t("common.save")}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <Input
          label={t("owner.tenants.storeName")}
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <div className="grid grid-cols-2 gap-4">
          <Input
            label={t("owner.tenants.ownerEmail")}
            type="email"
            value={ownerEmail}
            onChange={(e) => setOwnerEmail(e.target.value)}
          />
          <Input
            label={t("owner.tenants.ownerPhone")}
            value={ownerPhone}
            onChange={(e) => setOwnerPhone(e.target.value)}
          />
        </div>
        <Select
          label={t("owner.tenants.plan")}
          value={planCode}
          onChange={(e) => setPlanCode(e.target.value as PlanCode)}
        >
          <option value="lite">{t("plans.lite")}</option>
          <option value="pro">{t("plans.pro")}</option>
          <option value="pro_max">{t("plans.pro_max")}</option>
        </Select>
        <Input
          label={t("owner.tenants.storeLocationName")}
          value={storeName}
          onChange={(e) => setStoreName(e.target.value)}
          placeholder={t("owner.tenants.storeLocationPlaceholder", { name: name || "Store" })}
        />

        <div className="border-t border-slate-200 pt-4">
          <p className="mb-3 text-sm font-medium text-slate-700">{t("owner.tenants.firstAdmin")}</p>
          <div className="flex flex-col gap-4">
            <Input
              label={t("owner.tenants.adminName")}
              value={adminName}
              onChange={(e) => setAdminName(e.target.value)}
            />
            <div className="grid grid-cols-2 gap-4">
              <Input
                label={t("owner.tenants.adminEmail")}
                type="email"
                value={adminEmail}
                onChange={(e) => setAdminEmail(e.target.value)}
              />
              <Input
                label={t("owner.tenants.adminPassword")}
                type="password"
                value={adminPassword}
                onChange={(e) => setAdminPassword(e.target.value)}
              />
            </div>
          </div>
        </div>

        {error && <p className="text-sm text-danger-600">{error}</p>}
      </div>
    </Modal>
  );
}
