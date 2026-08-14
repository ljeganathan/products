// RawBT transport for "rawbt"-connection printers — hands raw ESC/POS bytes off to the
// free RawBT Android app (https://rawbt.ru), which does the actual printer connection
// itself (WiFi/network, Classic or BLE Bluetooth, or USB) using Android's native
// networking stack — not the browser's, so it isn't limited by mixed-content blocking
// (WiFi/network printers) or BLE-only support (Web Bluetooth, utils/webBluetoothPrinter.ts).
// This is the most robust option for a WiFi thermal printer reached from a
// cashier's Android tablet, since the print job never has to leave the tablet's own LAN.
//
// Setup is entirely inside the RawBT app on the Android device — install it from the
// Play Store, configure its default printer connection there — so there's nothing to
// pair or configure on StoreMate's side; this transport just hands off bytes every time.
//
// Intent URL format confirmed against mike42/escpos-php's RawbtPrintConnector, an
// established open-source ESC/POS library with a maintained RawBT integration:
//   intent:base64,<BASE64_DATA>#Intent;scheme=rawbt;package=ru.a402d.rawbtprinter;end;
const RAWBT_PACKAGE = "ru.a402d.rawbtprinter";

function buildRawbtIntentUrl(dataBase64: string): string {
  return `intent:base64,${dataBase64}#Intent;scheme=rawbt;package=${RAWBT_PACKAGE};end;`;
}

// Navigating to an intent: URL hands the OS off to RawBT if it's installed; if it
// isn't, Chrome on Android silently no-ops the navigation (no page-visible error) — the
// caller can't distinguish "printed" from "RawBT not installed" this way, same
// limitation the underlying platform has, so the cashier-facing copy tells them to
// confirm on the printer itself.
export async function sendPrintJobViaRawbt(dataBase64: string): Promise<void> {
  window.location.href = buildRawbtIntentUrl(dataBase64);
}
