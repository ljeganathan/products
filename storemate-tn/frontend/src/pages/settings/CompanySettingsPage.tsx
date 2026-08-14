import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  getCompanySettings,
  updateCompanySettings,
  uploadCompanyLogo,
  type CompanySettingsUpdate,
} from "@/api/companySettings";
import { resolveMediaUrl } from "@/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/ui/PageHeader";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { buildSampleReceiptPayload } from "@/features/settings/sampleReceipt";
import { toast } from "@/store/toastStore";
import { buildReceiptLines } from "@/utils/receiptLayout";
import { getApiErrorMessage } from "@/utils/apiError";

export default function CompanySettingsPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: company, isLoading } = useQuery({
    queryKey: ["company-settings"],
    queryFn: () => getCompanySettings(),
  });

  const [form, setForm] = useState<CompanySettingsUpdate>({});
  const [isSaving, setIsSaving] = useState(false);
  const [isUploadingLogo, setIsUploadingLogo] = useState(false);

  useEffect(() => {
    if (!company) return;
    setForm({
      legal_name: company.legal_name,
      display_name: company.display_name,
      address: company.address,
      pincode: company.pincode ?? "",
      gstin: company.gstin ?? "",
      fssai_no: company.fssai_no ?? "",
      phone: company.phone ?? "",
      invoice_footer_text: company.invoice_footer_text ?? "",
      show_tamil_item_names: company.show_tamil_item_names,
      upi_vpa: company.upi_vpa ?? "",
      show_upi_qr: company.show_upi_qr,
    });
  }, [company]);

  function setField<K extends keyof CompanySettingsUpdate>(key: K, value: CompanySettingsUpdate[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  const PINCODE_PATTERN = /^[1-9][0-9]{5}$/;

  async function handleSave() {
    if (!form.pincode || !PINCODE_PATTERN.test(form.pincode)) {
      toast("danger", t("settings.company.pincodeRequired"));
      return;
    }
    setIsSaving(true);
    try {
      await updateCompanySettings({ ...form, show_upi_qr: form.upi_vpa ? form.show_upi_qr : false });
      await queryClient.invalidateQueries({ queryKey: ["company-settings"] });
      toast("success", t("common.saved"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("common.saveError")));
    } finally {
      setIsSaving(false);
    }
  }

  async function handleLogoUpload(file: File) {
    setIsUploadingLogo(true);
    try {
      await uploadCompanyLogo(file);
      await queryClient.invalidateQueries({ queryKey: ["company-settings"] });
      toast("success", t("settings.company.logoUploaded"));
    } catch (err) {
      toast("danger", getApiErrorMessage(err, t("settings.company.logoUploadError")));
    } finally {
      setIsUploadingLogo(false);
    }
  }

  const previewLines =
    company && !isLoading
      ? buildReceiptLines(
          buildSampleReceiptPayload({
            ...company,
            legal_name: form.legal_name ?? company.legal_name,
            display_name: form.display_name ?? company.display_name,
            address: form.address ?? company.address,
            pincode: (form.pincode ?? company.pincode) || null,
            gstin: (form.gstin ?? company.gstin) || null,
            phone: (form.phone ?? company.phone) || null,
            invoice_footer_text: (form.invoice_footer_text ?? company.invoice_footer_text) || null,
            show_tamil_item_names: form.show_tamil_item_names ?? company.show_tamil_item_names,
          }),
          42,
        )
      : [];

  if (isLoading) {
    return <p className="text-slate-500">{t("common.loading")}</p>;
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title={t("settings.company.title")} subtitle={t("settings.company.subtitle")} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="flex flex-col gap-4 lg:col-span-2">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label={t("settings.company.legalName")}
              value={form.legal_name ?? ""}
              onChange={(e) => setField("legal_name", e.target.value)}
            />
            <Input
              label={t("settings.company.displayName")}
              value={form.display_name ?? ""}
              onChange={(e) => setField("display_name", e.target.value)}
            />
          </div>
          <Textarea
            label={t("settings.company.address")}
            value={form.address ?? ""}
            onChange={(e) => setField("address", e.target.value)}
          />
          <Input
            label={`${t("settings.company.pincode")} *`}
            value={form.pincode ?? ""}
            required
            maxLength={6}
            inputMode="numeric"
            error={
              form.pincode && !PINCODE_PATTERN.test(form.pincode)
                ? t("settings.company.pincodeInvalid")
                : undefined
            }
            onChange={(e) => setField("pincode", e.target.value.replace(/\D/g, ""))}
          />
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Input
              label={t("settings.company.gstin")}
              value={form.gstin ?? ""}
              onChange={(e) => setField("gstin", e.target.value)}
            />
            <Input
              label={t("settings.company.fssaiNo")}
              value={form.fssai_no ?? ""}
              onChange={(e) => setField("fssai_no", e.target.value)}
            />
            <Input
              label={t("settings.company.phone")}
              value={form.phone ?? ""}
              onChange={(e) => setField("phone", e.target.value)}
            />
          </div>
          <Textarea
            label={t("settings.company.footerText")}
            value={form.invoice_footer_text ?? ""}
            onChange={(e) => setField("invoice_footer_text", e.target.value)}
          />

          <div className="flex flex-col gap-1.5">
            <Select
              label={t("settings.company.itemNameLanguage")}
              value={(form.show_tamil_item_names ?? false) ? "ta" : "en"}
              onChange={(e) => setField("show_tamil_item_names", e.target.value === "ta")}
            >
              <option value="en">{t("settings.company.itemNameLanguageEnglish")}</option>
              <option value="ta">{t("settings.company.itemNameLanguageTamil")}</option>
            </Select>
            <p className="text-xs text-slate-500">{t("settings.company.itemNameLanguageHint")}</p>
          </div>

          <Input
            label={t("settings.company.upiVpa")}
            placeholder="store@okhdfcbank"
            value={form.upi_vpa ?? ""}
            onChange={(e) => setField("upi_vpa", e.target.value)}
          />

          <label className="flex items-start gap-3 rounded-lg border border-slate-200 bg-white px-3 py-2.5">
            <input
              type="checkbox"
              checked={form.show_upi_qr ?? false}
              onChange={(e) => setField("show_upi_qr", e.target.checked)}
              disabled={!form.upi_vpa}
              className="mt-0.5 h-4 w-4 rounded border-slate-300"
            />
            <span>
              <span className="block text-sm font-medium text-slate-700">
                {t("settings.company.showUpiQr")}
              </span>
              <span className="block text-xs text-slate-500">{t("settings.company.showUpiQrHint")}</span>
            </span>
          </label>

          <div>
            <label className="mb-1.5 block text-sm font-medium text-slate-700">
              {t("settings.company.logo")}
            </label>
            <div className="flex items-center gap-4">
              {company?.logo_url && (
                <img
                  src={resolveMediaUrl(company.logo_url)}
                  alt={company.display_name}
                  className="h-16 w-16 rounded-lg border border-slate-200 object-contain p-1"
                />
              )}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) void handleLogoUpload(file);
                }}
              />
              <Button
                variant="outline"
                onClick={() => fileInputRef.current?.click()}
                isLoading={isUploadingLogo}
              >
                <Upload className="h-4 w-4" />
                {t("settings.company.uploadLogo")}
              </Button>
            </div>
          </div>

          <Button onClick={() => void handleSave()} isLoading={isSaving} className="w-fit">
            {t("common.save")}
          </Button>
        </div>

        <div>
          <p className="mb-2 text-sm font-medium text-slate-700">{t("settings.company.receiptPreview")}</p>
          <div className="overflow-x-auto rounded-lg border border-slate-200 bg-slate-50 p-4">
            {company?.logo_url && (
              <img
                src={resolveMediaUrl(company.logo_url)}
                alt={company.display_name}
                className="mx-auto mb-2 h-14 object-contain"
              />
            )}
            <pre className="whitespace-pre font-mono text-xs leading-relaxed text-slate-800">
              {previewLines.slice(0, 8).join("\n")}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}
