import { useEffect, useRef } from "react";

export interface KeyboardShortcutHandlers {
  openHelp: () => void;
  focusSearch: () => void;
  focusManualEntry: () => void;
  applyBillDiscount: () => void;
  applyItemDiscount: () => void;
  incrementQty: () => void;
  decrementQty: () => void;
  removeSelectedLine: () => void;
  undoRemove: () => void;
  holdBill: () => void;
  recallHeldBills: () => void;
  finalizeBill: () => void;
  cancelBill: () => void;
}

function isTypingTarget(el: Element | null): boolean {
  if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) return true;
  return (el as HTMLElement | null)?.isContentEditable === true;
}

/** The full POS shortcut map (see HelpOverlay for the on-screen reference,
 * opened by F1). F-keys, Ctrl+Enter/Z, and Esc work everywhere including
 * while a field has focus — they're never characters a cashier would be
 * typing. Qty +/-/Delete only fire when nothing is being typed into, so
 * they don't clobber a customer-phone or search field. */
export function useKeyboardShortcuts(handlers: KeyboardShortcutHandlers, enabled = true): void {
  const handlersRef = useRef(handlers);
  handlersRef.current = handlers;

  useEffect(() => {
    if (!enabled) return;

    function handleKeyDown(e: KeyboardEvent) {
      const h = handlersRef.current;

      switch (e.key) {
        case "F1":
          e.preventDefault();
          h.openHelp();
          return;
        case "F2":
          e.preventDefault();
          h.focusSearch();
          return;
        case "F3":
          e.preventDefault();
          h.focusManualEntry();
          return;
        case "F4":
          e.preventDefault();
          h.applyBillDiscount();
          return;
        case "F5":
          e.preventDefault();
          h.applyItemDiscount();
          return;
        case "F8":
          e.preventDefault();
          h.holdBill();
          return;
        case "F9":
          e.preventDefault();
          h.recallHeldBills();
          return;
        case "F10":
          e.preventDefault();
          h.finalizeBill();
          return;
        case "Escape":
          e.preventDefault();
          h.cancelBill();
          return;
      }

      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
        e.preventDefault();
        h.finalizeBill();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        h.undoRemove();
        return;
      }

      if (isTypingTarget(document.activeElement)) return;

      if ((e.ctrlKey || e.metaKey) && e.key === "ArrowUp") {
        e.preventDefault();
        h.incrementQty();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key === "ArrowDown") {
        e.preventDefault();
        h.decrementQty();
        return;
      }
      if (e.key === "+" || e.key === "=") {
        e.preventDefault();
        h.incrementQty();
        return;
      }
      if (e.key === "-") {
        e.preventDefault();
        h.decrementQty();
        return;
      }
      if (e.key === "Delete") {
        e.preventDefault();
        h.removeSelectedLine();
      }
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [enabled]);
}
