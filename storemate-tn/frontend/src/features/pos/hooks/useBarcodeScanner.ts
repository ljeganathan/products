import { useEffect, useRef } from "react";

// Real HID barcode scanners emit characters back-to-back in single-digit
// milliseconds; even a fast human typist rarely sustains under ~80ms/char
// across a whole code. Anything averaging at or under this is treated as a
// scan rather than manual keystrokes landing on the page by accident.
const SCAN_MAX_AVG_INTERVAL_MS = 50;
const BURST_RESET_GAP_MS = 300;
const MIN_CODE_LENGTH = 3;

function isTypingTarget(el: Element | null): boolean {
  if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) return true;
  return (el as HTMLElement | null)?.isContentEditable === true;
}

/** Listens globally for scanner-speed keystroke bursts ending in Enter and
 * reports the scanned code — active whenever no visible text field has
 * focus, so it never fights with manual typing in the search/qty/customer
 * inputs (those own their own onKeyDown for Enter-to-submit). */
export function useBarcodeScanner(onScan: (code: string) => void, enabled = true): void {
  const bufferRef = useRef("");
  const timestampsRef = useRef<number[]>([]);
  const onScanRef = useRef(onScan);
  onScanRef.current = onScan;

  useEffect(() => {
    if (!enabled) return;

    function reset() {
      bufferRef.current = "";
      timestampsRef.current = [];
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (isTypingTarget(document.activeElement)) return;

      if (e.key === "Enter") {
        const code = bufferRef.current;
        const timestamps = timestampsRef.current;
        reset();
        if (code.length < MIN_CODE_LENGTH || timestamps.length < 2) return;

        const intervals: number[] = [];
        for (let i = 1; i < timestamps.length; i++) intervals.push(timestamps[i] - timestamps[i - 1]);
        const avgInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length;

        if (avgInterval <= SCAN_MAX_AVG_INTERVAL_MS) {
          onScanRef.current(code);
        }
        return;
      }

      if (e.key.length !== 1) return; // ignore Shift/Tab/F-keys/arrows/etc.

      const now = performance.now();
      const last = timestampsRef.current.at(-1);
      if (last !== undefined && now - last > BURST_RESET_GAP_MS) reset();
      bufferRef.current += e.key;
      timestampsRef.current.push(now);
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [enabled]);
}
