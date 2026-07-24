import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { DiscountType, PaymentMode, ResumeBillResponse } from "@/types/bill";
import type { Item, TaxProfile } from "@/types/item";

type TaxProfileLookup = (taxProfileId: string) => TaxProfile | undefined;

export interface CartLine {
  itemId: string;
  nameEn: string;
  nameTa: string;
  unit: string;
  barcode: string | null;
  unitPricePaise: number;
  qty: number;
  cgstPct: number;
  sgstPct: number;
  igstPct: number;
  discountType: DiscountType | null;
  discountValue: number | null;
}

interface CartState {
  lines: CartLine[];
  selectedIndex: number | null;
  customerName: string;
  customerPhone: string;
  paymentMode: PaymentMode;
  billDiscountType: DiscountType | null;
  billDiscountValue: number | null;
  lastRemoved: { line: CartLine; index: number } | null;

  addItem: (item: Item, taxProfile: TaxProfile | undefined, qty?: number) => void;
  selectLine: (index: number | null) => void;
  setQty: (index: number, qty: number) => void;
  adjustQty: (index: number, delta: number) => void;
  removeLine: (index: number) => void;
  undoRemove: () => void;
  setLineDiscount: (index: number, type: DiscountType | null, value: number | null) => void;
  setBillDiscount: (type: DiscountType | null, value: number | null) => void;
  setCustomer: (name: string, phone: string) => void;
  setPaymentMode: (mode: PaymentMode) => void;
  loadResumedBill: (
    resumed: ResumeBillResponse,
    itemLookup: (id: string) => Item | undefined,
    taxProfileLookup: TaxProfileLookup,
  ) => void;
  clear: () => void;
}

const initialState = {
  lines: [] as CartLine[],
  selectedIndex: null as number | null,
  customerName: "",
  customerPhone: "",
  paymentMode: "cash" as PaymentMode,
  billDiscountType: null as DiscountType | null,
  billDiscountValue: null as number | null,
  lastRemoved: null as { line: CartLine; index: number } | null,
};

export const useCartStore = create<CartState>()(
  persist(
    (set, get) => ({
      ...initialState,

      addItem: (item, taxProfile, qty = 1) =>
        set((state) => {
          const existingIndex = state.lines.findIndex((l) => l.itemId === item.id);
          if (existingIndex >= 0) {
            const lines = [...state.lines];
            lines[existingIndex] = { ...lines[existingIndex], qty: lines[existingIndex].qty + qty };
            return { lines, selectedIndex: existingIndex };
          }
          const line: CartLine = {
            itemId: item.id,
            nameEn: item.name_en,
            nameTa: item.name_ta,
            unit: item.unit,
            barcode: item.barcode,
            unitPricePaise: item.selling_price_paise,
            qty,
            cgstPct: taxProfile?.cgst_pct ?? 0,
            sgstPct: taxProfile?.sgst_pct ?? 0,
            igstPct: taxProfile?.igst_pct ?? 0,
            discountType: null,
            discountValue: null,
          };
          return { lines: [...state.lines, line], selectedIndex: state.lines.length };
        }),

      selectLine: (index) => set({ selectedIndex: index }),

      setQty: (index, qty) =>
        set((state) => {
          if (qty <= 0) return state;
          const lines = [...state.lines];
          lines[index] = { ...lines[index], qty };
          return { lines };
        }),

      adjustQty: (index, delta) => {
        const line = get().lines[index];
        if (!line) return;
        const next = Math.round((line.qty + delta) * 1000) / 1000;
        if (next > 0) get().setQty(index, next);
      },

      removeLine: (index) =>
        set((state) => {
          const line = state.lines[index];
          if (!line) return state;
          const lines = state.lines.filter((_, i) => i !== index);
          return {
            lines,
            selectedIndex: null,
            lastRemoved: { line, index },
          };
        }),

      undoRemove: () =>
        set((state) => {
          if (!state.lastRemoved) return state;
          const lines = [...state.lines];
          lines.splice(state.lastRemoved.index, 0, state.lastRemoved.line);
          return { lines, lastRemoved: null, selectedIndex: state.lastRemoved.index };
        }),

      setLineDiscount: (index, type, value) =>
        set((state) => {
          const lines = [...state.lines];
          lines[index] = { ...lines[index], discountType: type, discountValue: value };
          return { lines };
        }),

      setBillDiscount: (type, value) => set({ billDiscountType: type, billDiscountValue: value }),

      setCustomer: (name, phone) => set({ customerName: name, customerPhone: phone }),

      setPaymentMode: (mode) => set({ paymentMode: mode }),

      loadResumedBill: (resumed, itemLookup, taxProfileLookup) =>
        set(() => {
          const lines: CartLine[] = [];
          for (const line of resumed.items) {
            const item = itemLookup(line.item_id);
            if (!item) continue;
            const taxProfile = taxProfileLookup(item.tax_profile_id);
            lines.push({
              itemId: item.id,
              nameEn: item.name_en,
              nameTa: item.name_ta,
              unit: item.unit,
              barcode: item.barcode,
              unitPricePaise: item.selling_price_paise,
              qty: line.qty,
              cgstPct: taxProfile?.cgst_pct ?? 0,
              sgstPct: taxProfile?.sgst_pct ?? 0,
              igstPct: taxProfile?.igst_pct ?? 0,
              discountType: line.discount_type ?? null,
              discountValue: line.discount_value ?? null,
            });
          }
          return {
            ...initialState,
            lines,
            customerName: resumed.customer_name ?? "",
            customerPhone: resumed.customer_phone ?? "",
            paymentMode: resumed.payment_mode,
          };
        }),

      clear: () => set({ ...initialState }),
    }),
    {
      // Survives an accidental refresh mid-sale; the *explicit* hold/resume
      // flow (F8/F9) is additionally backed by the server (bills.status =
      // held), which is the real guarantee behind the DoD requirement.
      name: "storemate-pos-cart",
    },
  ),
);
