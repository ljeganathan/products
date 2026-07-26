import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { createBill, getBill, printBill, resumeBill } from "@/api/bills";
import { getCompanySettings } from "@/api/companySettings";
import { listPrinterProfiles } from "@/api/printerProfiles";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Input";
import { Modal } from "@/components/ui/Modal";
import { CartTable } from "@/features/pos/components/CartTable";
import { DiscountModal } from "@/features/pos/components/DiscountModal";
import { HeldBillsModal } from "@/features/pos/components/HeldBillsModal";
import { HelpOverlay } from "@/features/pos/components/HelpOverlay";
import { ItemSearchBar } from "@/features/pos/components/ItemSearchBar";
import { ManualEntryInput } from "@/features/pos/components/ManualEntryInput";
import { PrintPreviewModal } from "@/features/pos/components/PrintPreviewModal";
import { QuantityEntryModal } from "@/features/pos/components/QuantityEntryModal";
import { SavedBillDetailModal } from "@/features/pos/components/SavedBillDetailModal";
import { SavedBillSearchModal } from "@/features/pos/components/SavedBillSearchModal";
import { TotalsPanel } from "@/features/pos/components/TotalsPanel";
import { useBarcodeScanner } from "@/features/pos/hooks/useBarcodeScanner";
import { useItemCatalog } from "@/features/pos/hooks/useItemCatalog";
import { useKeyboardShortcuts } from "@/features/pos/hooks/useKeyboardShortcuts";
import { useStockLookup } from "@/features/pos/hooks/useStockLookup";
import { dispatchPrint } from "@/features/pos/printDispatch";
import { useAuthStore } from "@/store/authStore";
import { useCartStore } from "@/store/cartStore";
import { toast } from "@/store/toastStore";
import type { Bill, BillPrintPayload } from "@/types/bill";
import type { Item } from "@/types/item";
import { getApiErrorMessage } from "@/utils/apiError";
import { computeBillTotals } from "@/utils/billingCalc";

const AUTO_PRINT_STORAGE_KEY = "storemate-pos-autoprint";

export default function PosPage() {
  const { t } = useTranslation();
  const storeId = useAuthStore((s) => s.user?.store_id ?? undefined);
  const catalog = useItemCatalog(storeId);
  const stock = useStockLookup(storeId);

  const cart = useCartStore();
  const companySettingsQuery = useQuery({
    queryKey: ["company-settings"],
    queryFn: () => getCompanySettings(),
  });
  const showTamilItemNames = companySettingsQuery.data?.show_tamil_item_names ?? false;
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [isHeldBillsOpen, setIsHeldBillsOpen] = useState(false);
  const [isSavedSearchOpen, setIsSavedSearchOpen] = useState(false);
  const [isCancelConfirmOpen, setIsCancelConfirmOpen] = useState(false);
  const [billDiscountModalOpen, setBillDiscountModalOpen] = useState(false);
  const [lineDiscountIndex, setLineDiscountIndex] = useState<number | null>(null);
  const [printPayload, setPrintPayload] = useState<BillPrintPayload | null>(null);
  const [pendingItem, setPendingItem] = useState<Item | null>(null);
  const [viewingBillId, setViewingBillId] = useState<string | null>(null);
  const [autoPrint, setAutoPrint] = useState<boolean>(() => {
    const saved = localStorage.getItem(AUTO_PRINT_STORAGE_KEY);
    return saved === null ? true : saved === "true";
  });

  useEffect(() => {
    localStorage.setItem(AUTO_PRINT_STORAGE_KEY, String(autoPrint));
  }, [autoPrint]);

  const viewingBillQuery = useQuery({
    queryKey: ["bill-detail", viewingBillId],
    queryFn: () => getBill(viewingBillId as string),
    enabled: viewingBillId !== null,
  });

  const searchRef = useRef<HTMLInputElement>(null);
  const manualRef = useRef<HTMLInputElement>(null);
  const cancelConfirmYesRef = useRef<HTMLButtonElement>(null);

  // While any modal is open, keyboard focus is conceptually "inside" it —
  // global shortcuts (and accidental barcode-scanner input) must not also
  // fire underneath, or Esc-to-close would simultaneously trigger e.g. the
  // cancel-bill confirmation and stack a second modal on top.
  const isAnyModalOpen =
    isHelpOpen ||
    isHeldBillsOpen ||
    isSavedSearchOpen ||
    isCancelConfirmOpen ||
    billDiscountModalOpen ||
    lineDiscountIndex !== null ||
    printPayload !== null ||
    pendingItem !== null ||
    viewingBillId !== null;

  const totals = computeBillTotals(
    cart.lines.map((l) => ({
      itemId: l.itemId,
      name: l.nameEn,
      unitPricePaise: l.unitPricePaise,
      qty: l.qty,
      cgstPct: l.cgstPct,
      sgstPct: l.sgstPct,
      discountType: l.discountType,
      discountValue: l.discountValue,
    })),
    cart.billDiscountType,
    cart.billDiscountValue,
  );

  function promptAddItem(item: Item) {
    setPendingItem(item);
  }

  function confirmAddItem(qty: number) {
    if (!pendingItem) return;
    const taxProfile = catalog.getTaxProfile(pendingItem.tax_profile_id);
    cart.addItem(pendingItem, taxProfile, qty);
    setPendingItem(null);
  }

  const pendingItemCartQty = pendingItem
    ? (cart.lines.find((l) => l.itemId === pendingItem.id)?.qty ?? 0)
    : 0;

  useBarcodeScanner((code) => {
    const item = catalog.findByBarcode(code);
    if (item) {
      promptAddItem(item);
    } else {
      toast("danger", t("pos.itemNotFoundTitle"), t("pos.itemNotFoundDescription", { code }));
    }
  }, !!storeId && !isAnyModalOpen);

  useKeyboardShortcuts(
    {
      openHelp: () => setIsHelpOpen(true),
      focusSearch: () => searchRef.current?.focus(),
      focusManualEntry: () => manualRef.current?.focus(),
      applyBillDiscount: () => setBillDiscountModalOpen(true),
      applyItemDiscount: () => {
        if (cart.selectedIndex !== null) setLineDiscountIndex(cart.selectedIndex);
      },
      incrementQty: () => {
        if (cart.selectedIndex !== null) cart.adjustQty(cart.selectedIndex, 1);
      },
      decrementQty: () => {
        if (cart.selectedIndex !== null) cart.adjustQty(cart.selectedIndex, -1);
      },
      removeSelectedLine: () => {
        if (cart.selectedIndex !== null) cart.removeLine(cart.selectedIndex);
      },
      undoRemove: () => cart.undoRemove(),
      holdBill: () => void handleHold(),
      recallHeldBills: () => setIsHeldBillsOpen(true),
      finalizeBill: () => void handleFinalize(),
      cancelBill: () => {
        if (cart.lines.length > 0) setIsCancelConfirmOpen(true);
      },
    },
    !!storeId && !isAnyModalOpen,
  );

  async function handleHold() {
    if (cart.lines.length === 0 || isSubmitting) return;
    setIsSubmitting(true);
    try {
      const bill = await createBill({
        payment_mode: cart.paymentMode,
        customer_name: cart.customerName || null,
        customer_phone: cart.customerPhone || null,
        items: cart.lines.map((l) => ({
          item_id: l.itemId,
          qty: l.qty,
          discount_type: l.discountType,
          discount_value: l.discountValue,
        })),
        bill_discount_type: cart.billDiscountType,
        bill_discount_value: cart.billDiscountValue,
        hold: true,
      });
      cart.clear();
      toast("success", t("pos.billHeldTitle"), t("pos.billNumber", { number: bill.bill_number }));
    } catch (err) {
      toast("danger", t("pos.saveErrorTitle"), getApiErrorMessage(err, t("pos.billErrorTitle")));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function printAfterFinalize(billId: string) {
    const payload = await printBill(billId);
    if (!autoPrint) {
      setPrintPayload(payload);
      return;
    }
    try {
      const profiles = await listPrinterProfiles();
      const profile = profiles.find((p) => p.is_default) ?? profiles[0];
      if (!profile) {
        // Nothing configured to print to — fall back to the preview modal so
        // the cashier sees why nothing happened instead of a silent no-op.
        setPrintPayload(payload);
        return;
      }
      await dispatchPrint(profile, payload);
      toast("success", t("pos.printSuccessTitle"));
    } catch (err) {
      toast("danger", t("pos.printFailedTitle"), err instanceof Error ? err.message : undefined);
    }
  }

  async function handleFinalize() {
    if (cart.lines.length === 0 || isSubmitting) return;
    setIsSubmitting(true);
    try {
      const bill = await createBill({
        payment_mode: cart.paymentMode,
        customer_name: cart.customerName || null,
        customer_phone: cart.customerPhone || null,
        items: cart.lines.map((l) => ({
          item_id: l.itemId,
          qty: l.qty,
          discount_type: l.discountType,
          discount_value: l.discountValue,
        })),
        bill_discount_type: cart.billDiscountType,
        bill_discount_value: cart.billDiscountValue,
        hold: false,
      });
      cart.clear();
      await printAfterFinalize(bill.id);
    } catch (err) {
      toast("danger", t("pos.saveErrorTitle"), getApiErrorMessage(err, t("pos.billErrorTitle")));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleResume(billId: string) {
    setIsHeldBillsOpen(false);
    try {
      const resumed = await resumeBill(billId);
      cart.loadResumedBill(resumed, catalog.getItem, catalog.getTaxProfile);
    } catch (err) {
      toast("danger", t("pos.saveErrorTitle"), getApiErrorMessage(err, t("pos.billErrorTitle")));
    }
  }

  if (!storeId) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <EmptyState title={t("pos.noStoreTitle")} description={t("pos.noStoreDescription")} />
      </div>
    );
  }

  const selectedLine = cart.selectedIndex !== null ? cart.lines[cart.selectedIndex] : null;

  return (
    <div className="flex h-full flex-col gap-4 p-4 lg:flex-row">
      <div className="flex min-h-0 min-w-0 flex-1 flex-col gap-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <ItemSearchBar ref={searchRef} catalog={catalog} onSelect={promptAddItem} />
          <ManualEntryInput ref={manualRef} catalog={catalog} onFound={promptAddItem} />
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Input
            label={t("pos.customerName")}
            value={cart.customerName}
            onChange={(e) => cart.setCustomer(e.target.value, cart.customerPhone)}
          />
          <Input
            label={t("pos.customerPhone")}
            value={cart.customerPhone}
            onChange={(e) => cart.setCustomer(cart.customerName, e.target.value)}
          />
        </div>

        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => setIsSavedSearchOpen(true)}>
              {t("pos.savedBillSearch")}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setIsHeldBillsOpen(true)}>
              {t("pos.heldBillsTitle")}
            </Button>
          </div>
          <Button variant="ghost" size="sm" onClick={() => setIsHelpOpen(true)}>
            {t("pos.helpButton")} (F1)
          </Button>
        </div>

        <CartTable
          lines={cart.lines}
          lineResults={totals.lines}
          selectedIndex={cart.selectedIndex}
          showTamilItemNames={showTamilItemNames}
          onSelect={cart.selectLine}
          onQtyChange={cart.setQty}
          onAdjustQty={cart.adjustQty}
          onRemove={cart.removeLine}
          onOpenDiscount={setLineDiscountIndex}
        />
      </div>

      <div className="flex w-full flex-col gap-3 lg:w-80">
        <label className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-700">
          <input
            type="checkbox"
            checked={autoPrint}
            onChange={(e) => setAutoPrint(e.target.checked)}
            className="h-4 w-4 rounded border-slate-300"
          />
          {t("pos.printAutomatically")}
        </label>

        <TotalsPanel
          totals={totals}
          paymentMode={cart.paymentMode}
          onPaymentModeChange={cart.setPaymentMode}
          onOpenBillDiscount={() => setBillDiscountModalOpen(true)}
          onHold={() => void handleHold()}
          onFinalize={() => void handleFinalize()}
          onCancel={() => cart.lines.length > 0 && setIsCancelConfirmOpen(true)}
          isSubmitting={isSubmitting}
          disabled={cart.lines.length === 0}
        />
      </div>

      <HelpOverlay open={isHelpOpen} onOpenChange={setIsHelpOpen} />
      <HeldBillsModal open={isHeldBillsOpen} onOpenChange={setIsHeldBillsOpen} onResume={(id) => void handleResume(id)} />
      <SavedBillSearchModal
        open={isSavedSearchOpen}
        onOpenChange={setIsSavedSearchOpen}
        onViewBill={(bill: Bill) => {
          setIsSavedSearchOpen(false);
          setViewingBillId(bill.id);
        }}
      />
      <SavedBillDetailModal
        open={viewingBillId !== null}
        onOpenChange={(open) => !open && setViewingBillId(null)}
        bill={viewingBillQuery.data ?? null}
        isLoading={viewingBillQuery.isLoading}
        showTamilItemNames={showTamilItemNames}
      />
      <PrintPreviewModal
        open={printPayload !== null}
        onOpenChange={(open) => !open && setPrintPayload(null)}
        payload={printPayload}
      />
      <QuantityEntryModal
        open={pendingItem !== null}
        item={pendingItem}
        availableQty={pendingItem ? stock.getQuantity(pendingItem.id) : undefined}
        currentCartQty={pendingItemCartQty}
        onOpenChange={(open) => !open && setPendingItem(null)}
        onConfirm={confirmAddItem}
        finalFocusRef={searchRef}
      />

      <DiscountModal
        open={billDiscountModalOpen}
        title={t("pos.billDiscount")}
        initialType={cart.billDiscountType}
        initialValue={cart.billDiscountValue}
        onOpenChange={setBillDiscountModalOpen}
        onApply={cart.setBillDiscount}
      />
      <DiscountModal
        open={lineDiscountIndex !== null}
        title={t("pos.lineDiscount")}
        initialType={selectedLine?.discountType ?? null}
        initialValue={selectedLine?.discountValue ?? null}
        onOpenChange={(open) => !open && setLineDiscountIndex(null)}
        onApply={(type, value) => {
          if (lineDiscountIndex !== null) cart.setLineDiscount(lineDiscountIndex, type, value);
        }}
      />

      <Modal
        open={isCancelConfirmOpen}
        onOpenChange={setIsCancelConfirmOpen}
        title={t("pos.cancelConfirmTitle")}
        description={t("pos.cancelConfirmDescription")}
        initialFocusRef={cancelConfirmYesRef}
        footer={
          <>
            <Button variant="ghost" onClick={() => setIsCancelConfirmOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              ref={cancelConfirmYesRef}
              variant="danger"
              onClick={() => {
                cart.clear();
                setIsCancelConfirmOpen(false);
              }}
            >
              {t("pos.cancelConfirmAction")}
            </Button>
          </>
        }
      >
        <p className="text-sm text-slate-500">{t("pos.cancelConfirmBody")}</p>
      </Modal>
    </div>
  );
}
