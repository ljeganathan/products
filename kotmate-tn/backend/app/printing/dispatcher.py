import logging

from app.models import Printer
from app.printing import dotmatrix_raw, escpos_thermal
from app.printing.base import BillRenderData, KotTicketRenderData

logger = logging.getLogger("kotmate.printing")


def dispatch_bill_print(printer: Printer, bill: BillRenderData) -> None:
    """Mirrors `dispatch_kot_print` below — same no-physical-transport-yet allowance
    (dev/test logs what would be sent)."""
    if printer.printer_type == "thermal":
        content: bytes | str = escpos_thermal.render_bill(bill)
    else:
        content = dotmatrix_raw.render_bill(bill)

    logger.info(
        "Bill print job -> printer=%s type=%s connection=%s/%s bill=%s bytes=%d",
        printer.name,
        printer.printer_type,
        printer.connection_type,
        printer.connection_details,
        bill.bill_number,
        len(content),
    )


def dispatch_kot_print(printer: Printer, ticket: KotTicketRenderData) -> None:
    """Renders the ticket via the adapter matching `printer.printer_type` and dispatches
    it. No physical transport layer exists yet (no USB/network socket implementation) —
    dev/test environments log what would be sent, which is the documented allowance in
    Phase 08's acceptance criteria ("can be mocked/logged in dev without real hardware").
    Swapping this log line for a real transport later is a one-function change.
    """
    if printer.printer_type == "thermal":
        content: bytes | str = escpos_thermal.render_kot(ticket)
    else:
        content = dotmatrix_raw.render_kot(ticket)

    logger.info(
        "KOT print job -> printer=%s type=%s connection=%s/%s ticket=%s bytes=%d",
        printer.name,
        printer.printer_type,
        printer.connection_type,
        printer.connection_details,
        ticket.ticket_number,
        len(content),
    )
