import { sendPrintJobToAgent } from "@/lib/printAgent";
import { sendPrintJobViaBluetooth } from "@/lib/webBluetoothPrinter";
import { sendPrintJobViaWebUSB } from "@/lib/webusbPrinter";
import type { BillPrintJob } from "@/modules/pos/billsApi";

// Single entry point every screen that can trigger a bill print (BillingModal,
// BillHistoryPage reprint) should call — branches to the local print-agent
// (desktop/laptop with a Windows-driver printer), WebUSB, or Web Bluetooth (Chrome on
// Android/desktop with no local agent) based on how the printer is registered.
// Returns null on success, or a message safe to show the cashier on failure — never
// throws, since a print failure must never block a bill that's already been finalized.
export async function dispatchPrintJob(job: BillPrintJob | null): Promise<string | null> {
  if (!job) return null;
  try {
    if (job.connection_type === "usb") {
      await sendPrintJobViaWebUSB(job.connection_details, job.data_base64);
    } else if (job.connection_type === "bluetooth") {
      await sendPrintJobViaBluetooth(job.connection_details, job.data_base64);
    } else {
      await sendPrintJobToAgent(job);
    }
    return null;
  } catch (err) {
    return err instanceof Error ? err.message : "Couldn't print to the local printer.";
  }
}
