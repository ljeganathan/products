import { useCallback, useState } from "react";

// "Print kitchen tickets on this device" — per device, not per screen. Only a device whose
// browser is paired with the kitchen printer should turn this on, because the device that
// claims a ticket is the only one that can print it.
const STORAGE_KEY = "kot-print-station";

export function readKitchenPrintStation(defaultOn: boolean): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === null) return defaultOn;
    return stored === "on";
  } catch {
    return defaultOn;
  }
}

export function useKitchenPrintStation(defaultOn: boolean): [boolean, (on: boolean) => void] {
  const [on, setOn] = useState(() => readKitchenPrintStation(defaultOn));
  const update = useCallback((next: boolean) => {
    try {
      localStorage.setItem(STORAGE_KEY, next ? "on" : "off");
    } catch {
      /* private browsing: the setting then lasts only for this page visit */
    }
    setOn(next);
  }, []);
  return [on, update];
}
