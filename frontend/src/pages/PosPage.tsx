import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { createBill, printBill, resumeBill } from "@/api/bills";
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
import { SavedBillSearchModal } from "@/features/pos/components/SavedBillSearchModal";
import { TotalsPanel } from "@/features/pos/components/TotalsPanel";
import { useBarcodeScanner } from "@/features/pos/hooks/useBarcodeScanner";
import { useItemCatalog } from "@/features/pos/hooks/useItemCatalog";
import { useKeyboardShortcuts } from "@/features/pos/hooks/useKeyboardShortcuts";
import { useAuthStore } from "@/store/authStore";
import { useCartStore } from "@/store/cartStore";
import { toast } from "@/store/toastStore";
import type { BillPrintPayload } from "@/types/bill";
import type { Item } from "@/types/item";
import { computeBillTotals } from "@/utils/billingCalc";

export default function PosPage() {
  const { t } = useTranslation();
  const storeId = useAuthStore((s) => s.user?.store_id ?? undefined);
  const catalog = useItemCatalog(storeId);

  const cart = useCartStore();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [isHeldBillsOpen, setIsHeldBillsOpen] = useState(false);
  const [isSavedSearchOpen, setIsSavedSearchOpen] = useState(false);
  const [isCancelConfirmOpen, setIsCancelConfirmOpen] = useState(false);
  const [billDiscountModalOpen, setBillDiscountModalOpen] = useState(false);
  const [lineDiscountIndex, setLineDiscountIndex] = useState<number | null>(null);
  const [printPayload, setPrintPayload] = useState<BillPrintPayload | null>(null);

  const searchRef = useRef<HTMLInputElement>(null);
  const manualRef = useRef<HTMLInputElement>(null);

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
    printPayload !== null;

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

  function addItemToCart(item: Item) {
    const taxProfile = catalog.getTaxProfile(item.tax_profile_id);
    cart.addItem(item, taxProfile, 1);
  }

  useBarcodeScanner((code) => {
    const item = catalog.findByBarcode(code);
    if (item) {
      addItemToCart(item);
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
    } catch {
      toast("danger", t("pos.billErrorTitle"));
    } finally {
      setIsSubmitting(false);
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
      const payload = await printBill(bill.id);
      setPrintPayload(payload);
    } catch {
      toast("danger", t("pos.billErrorTitle"));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleResume(billId: string) {
    setIsHeldBillsOpen(false);
    try {
      const resumed = await resumeBill(billId);
      cart.loadResumedBill(resumed, catalog.getItem, catalog.getTaxProfile);
    } catch {
      toast("danger", t("pos.billErrorTitle"));
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
      <div className="flex min-w-0 flex-1 flex-col gap-4">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <ItemSearchBar ref={searchRef} catalog={catalog} onSelect={addItemToCart} />
          <ManualEntryInput ref={manualRef} catalog={catalog} onFound={addItemToCart} />
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

        <div className="flex items-center justify-between">
          <Button variant="ghost" size="sm" onClick={() => setIsSavedSearchOpen(true)}>
            {t("pos.savedBillSearch")}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setIsHelpOpen(true)}>
            {t("pos.helpButton")} (F1)
          </Button>
        </div>

        <CartTable
          lines={cart.lines}
          lineResults={totals.lines}
          selectedIndex={cart.selectedIndex}
          onSelect={cart.selectLine}
          onQtyChange={cart.setQty}
          onAdjustQty={cart.adjustQty}
          onRemove={cart.removeLine}
          onOpenDiscount={setLineDiscountIndex}
        />
      </div>

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

      <HelpOverlay open={isHelpOpen} onOpenChange={setIsHelpOpen} />
      <HeldBillsModal open={isHeldBillsOpen} onOpenChange={setIsHeldBillsOpen} onResume={(id) => void handleResume(id)} />
      <SavedBillSearchModal open={isSavedSearchOpen} onOpenChange={setIsSavedSearchOpen} />
      <PrintPreviewModal
        open={printPayload !== null}
        onOpenChange={(open) => !open && setPrintPayload(null)}
        payload={printPayload}
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
        footer={
          <>
            <Button variant="ghost" onClick={() => setIsCancelConfirmOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
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
