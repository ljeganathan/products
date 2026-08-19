import type { BillPrintJob } from "@/modules/pos/billsApi";

// Bridges to the local print-agent (print-agent/agent.py) for "local_agent"-connection
// printers — a desktop/laptop counter machine whose printer is registered as a normal
// Windows printer queue. The agent listens on localhost and forwards raw ESC/POS bytes
// to the Windows print spooler (CLAUDE.md §10). "usb"-connection printers instead go
// through lib/webusbPrinter.ts directly from the browser — see lib/printDispatch.ts for
// the branch between the two.
const DEFAULT_AGENT_PORT = 9123;

function agentBaseUrl(connectionDetails: Record<string, unknown>): string {
  const port = Number(connectionDetails.agent_port) || DEFAULT_AGENT_PORT;
  return `http://127.0.0.1:${port}`;
}

export function windowsPrinterName(connectionDetails: Record<string, unknown>): string | null {
  const name = connectionDetails.windows_printer_name;
  return typeof name === "string" && name.trim() ? name.trim() : null;
}

export async function isPrintAgentReachable(connectionDetails: Record<string, unknown>): Promise<boolean> {
  try {
    const res = await fetch(`${agentBaseUrl(connectionDetails)}/health`, { signal: AbortSignal.timeout(1500) });
    return res.ok;
  } catch {
    return false;
  }
}

// Throws with a message suitable for direct display to the cashier (no local agent
// running, wrong printer name, spooler error, etc.) — callers decide how to surface it.
export async function sendPrintJobToAgent(job: BillPrintJob): Promise<void> {
  const printerName = windowsPrinterName(job.connection_details);
  if (!printerName) {
    throw new Error("This printer has no Windows Printer Name configured — set it in Settings > Printers.");
  }

  let res: Response;
  try {
    res = await fetch(`${agentBaseUrl(job.connection_details)}/print`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        printer_name: printerName,
        data_base64: job.data_base64,
        paper_width_mm: job.paper_width_mm,
      }),
      signal: AbortSignal.timeout(10_000),
    });
  } catch {
    throw new Error(
      "Couldn't reach the local print-agent on this machine — make sure it's running (see print-agent/README.md).",
    );
  }

  if (!res.ok) {
    const detail = await res.json().catch(() => null);
    throw new Error(detail?.detail ?? `Print agent returned ${res.status}`);
  }
}
