import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import type { Category, CategoryCreate } from "@/types/category";

export interface CategoryFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  category: Category | null;
  categories: Category[];
  onSubmit: (payload: CategoryCreate) => Promise<void>;
  isSubmitting: boolean;
}

export function CategoryFormModal({
  open,
  onOpenChange,
  category,
  categories,
  onSubmit,
  isSubmitting,
}: CategoryFormModalProps) {
  const { t } = useTranslation();
  const [nameEn, setNameEn] = useState("");
  const [nameTa, setNameTa] = useState("");
  const [parentId, setParentId] = useState("");
  const [hsnCode, setHsnCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setNameEn(category?.name_en ?? "");
    setNameTa(category?.name_ta ?? "");
    setParentId(category?.parent_category_id ?? "");
    setHsnCode(category?.hsn_code ?? "");
    setError(null);
  }, [open, category]);

  async function handleSubmit() {
    if (!nameEn.trim() || !nameTa.trim()) {
      setError(t("categories.namesRequired"));
      return;
    }
    await onSubmit({
      name_en: nameEn.trim(),
      name_ta: nameTa.trim(),
      parent_category_id: parentId || null,
      hsn_code: hsnCode.trim() || null,
    });
  }

  const selectableParents = categories.filter((c) => c.id !== category?.id);

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={category ? t("categories.editTitle") : t("categories.addTitle")}
      footer={
        <Button onClick={() => void handleSubmit()} isLoading={isSubmitting}>
          {t("common.save")}
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <Input
          label={t("categories.nameEn")}
          value={nameEn}
          onChange={(e) => setNameEn(e.target.value)}
        />
        <Input
          label={t("categories.nameTa")}
          value={nameTa}
          onChange={(e) => setNameTa(e.target.value)}
        />
        <Select
          label={t("categories.parentCategory")}
          value={parentId}
          onChange={(e) => setParentId(e.target.value)}
        >
          <option value="">{t("categories.noParent")}</option>
          {selectableParents.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name_en}
            </option>
          ))}
        </Select>
        <Input
          label={t("categories.hsnCode")}
          value={hsnCode}
          onChange={(e) => setHsnCode(e.target.value)}
        />
        {error && <p className="text-sm text-danger-600">{error}</p>}
      </div>
    </Modal>
  );
}
