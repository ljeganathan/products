import { ScanLine } from "lucide-react";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { Select } from "@/components/ui/Select";
import { useBarcodeScanner } from "@/features/pos/hooks/useBarcodeScanner";
import { toast } from "@/store/toastStore";
import type { Category } from "@/types/category";
import type { Item, ItemCreate, ItemUnit, TaxProfile } from "@/types/item";

const UNITS: ItemUnit[] = ["pcs", "kg", "g", "l", "ml", "box", "pack"];

export interface ItemFormModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: Item | null;
  categories: Category[];
  taxProfiles: TaxProfile[];
  onSubmit: (payload: ItemCreate) => Promise<void>;
  isSubmitting: boolean;
}

function paiseToRupeeString(paise: number | undefined): string {
  if (paise === undefined) return "";
  return (paise / 100).toString();
}

function rupeeStringToPaise(value: string): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? Math.round(parsed * 100) : 0;
}

export function ItemFormModal({
  open,
  onOpenChange,
  item,
  categories,
  taxProfiles,
  onSubmit,
  isSubmitting,
}: ItemFormModalProps) {
  const { t } = useTranslation();
  const [categoryId, setCategoryId] = useState("");
  const [nameEn, setNameEn] = useState("");
  const [nameTa, setNameTa] = useState("");
  const [sku, setSku] = useState("");
  const [barcode, setBarcode] = useState("");
  const [unit, setUnit] = useState<ItemUnit>("pcs");
  const [mrp, setMrp] = useState("");
  const [sellingPrice, setSellingPrice] = useState("");
  const [costPrice, setCostPrice] = useState("");
  const [taxProfileId, setTaxProfileId] = useState("");
  const [reorderLevel, setReorderLevel] = useState("0");
  const [reorderQty, setReorderQty] = useState("0");
  const [brand, setBrand] = useState("");
  const [packSize, setPackSize] = useState("");
  const [hsnCode, setHsnCode] = useState("");
  const [openingStock, setOpeningStock] = useState("0");
  const [isScanMode, setIsScanMode] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setCategoryId(item?.category_id ?? categories[0]?.id ?? "");
    setNameEn(item?.name_en ?? "");
    setNameTa(item?.name_ta ?? "");
    setSku(item?.sku ?? "");
    setBarcode(item?.barcode ?? "");
    setUnit(item?.unit ?? "pcs");
    setMrp(paiseToRupeeString(item?.mrp_paise));
    setSellingPrice(paiseToRupeeString(item?.selling_price_paise));
    setCostPrice(paiseToRupeeString(item?.cost_price_paise));
    setTaxProfileId(item?.tax_profile_id ?? taxProfiles.find((p) => p.is_default)?.id ?? taxProfiles[0]?.id ?? "");
    setReorderLevel(String(item?.reorder_level ?? 0));
    setReorderQty(String(item?.reorder_qty ?? 0));
    setBrand(item?.brand ?? "");
    setPackSize(item?.pack_size ?? "");
    setHsnCode(item?.hsn_code ?? "");
    setOpeningStock("0");
    setIsScanMode(false);
    setError(null);
  }, [open, item, categories, taxProfiles]);

  useBarcodeScanner((code) => {
    setBarcode(code);
    setIsScanMode(false);
    toast("success", t("items.scanCaptured"), code);
  }, isScanMode);

  async function handleSubmit() {
    if (!nameEn.trim() || !nameTa.trim()) {
      setError(t("items.namesRequired"));
      return;
    }
    if (!categoryId || !taxProfileId) {
      setError(t("items.categoryAndTaxRequired"));
      return;
    }
    setError(null);
    await onSubmit({
      category_id: categoryId,
      name_en: nameEn.trim(),
      name_ta: nameTa.trim(),
      sku: sku.trim() || null,
      barcode: barcode.trim() || null,
      unit,
      mrp_paise: rupeeStringToPaise(mrp),
      selling_price_paise: rupeeStringToPaise(sellingPrice),
      cost_price_paise: rupeeStringToPaise(costPrice),
      tax_profile_id: taxProfileId,
      reorder_level: Number(reorderLevel) || 0,
      reorder_qty: Number(reorderQty) || 0,
      brand: brand.trim() || null,
      pack_size: packSize.trim() || null,
      hsn_code: hsnCode.trim() || null,
      opening_stock: item ? 0 : Number(openingStock) || 0,
    });
  }

  return (
    <Modal
      open={open}
      onOpenChange={onOpenChange}
      title={item ? t("items.editTitle") : t("items.addTitle")}
      className="max-w-2xl"
      footer={
        <Button onClick={() => void handleSubmit()} isLoading={isSubmitting}>
          {t("common.save")}
        </Button>
      }
    >
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Input label={t("items.nameEn")} value={nameEn} onChange={(e) => setNameEn(e.target.value)} />
        <Input label={t("items.nameTa")} value={nameTa} onChange={(e) => setNameTa(e.target.value)} />

        <Select label={t("items.category")} value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
          {categories.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name_en}
            </option>
          ))}
        </Select>
        <Select
          label={t("items.taxProfile")}
          value={taxProfileId}
          onChange={(e) => setTaxProfileId(e.target.value)}
        >
          {taxProfiles.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </Select>

        <div className="relative">
          <Input
            label={t("items.barcode")}
            value={barcode}
            onChange={(e) => setBarcode(e.target.value)}
            className="pr-11"
          />
          <button
            type="button"
            onClick={() => setIsScanMode((v) => !v)}
            className={`absolute right-2 top-8 flex h-8 w-8 items-center justify-center rounded-lg ${
              isScanMode ? "bg-brand-600 text-white" : "text-slate-400 hover:bg-slate-100"
            }`}
            aria-label={t("items.scanToFill")}
            title={t("items.scanToFill")}
          >
            <ScanLine className="h-4 w-4" />
          </button>
        </div>
        <Input label={t("items.sku")} value={sku} onChange={(e) => setSku(e.target.value)} />

        {isScanMode && (
          <p className="col-span-full -mt-2 text-sm text-brand-600">{t("items.scanPrompt")}</p>
        )}

        <Select label={t("items.unit")} value={unit} onChange={(e) => setUnit(e.target.value as ItemUnit)}>
          {UNITS.map((u) => (
            <option key={u} value={u}>
              {u}
            </option>
          ))}
        </Select>
        <Input label={t("items.brand")} value={brand} onChange={(e) => setBrand(e.target.value)} />

        <Input
          type="number"
          min="0"
          step="0.01"
          label={t("items.mrp")}
          value={mrp}
          onChange={(e) => setMrp(e.target.value)}
        />
        <Input
          type="number"
          min="0"
          step="0.01"
          label={t("items.sellingPrice")}
          value={sellingPrice}
          onChange={(e) => setSellingPrice(e.target.value)}
        />
        <Input
          type="number"
          min="0"
          step="0.01"
          label={t("items.costPrice")}
          value={costPrice}
          onChange={(e) => setCostPrice(e.target.value)}
        />
        <Input label={t("items.packSize")} value={packSize} onChange={(e) => setPackSize(e.target.value)} />

        <Input
          type="number"
          min="0"
          step="0.001"
          label={t("items.reorderLevel")}
          value={reorderLevel}
          onChange={(e) => setReorderLevel(e.target.value)}
        />
        <Input
          type="number"
          min="0"
          step="0.001"
          label={t("items.reorderQty")}
          value={reorderQty}
          onChange={(e) => setReorderQty(e.target.value)}
        />

        <Input label={t("items.hsnCode")} value={hsnCode} onChange={(e) => setHsnCode(e.target.value)} />
        {!item && (
          <Input
            type="number"
            min="0"
            step="0.001"
            label={t("items.openingStock")}
            value={openingStock}
            onChange={(e) => setOpeningStock(e.target.value)}
          />
        )}
      </div>
      {error && <p className="mt-3 text-sm text-danger-600">{error}</p>}
    </Modal>
  );
}
