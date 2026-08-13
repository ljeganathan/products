import logging

from app.models import Printer
from app.printing import dotmatrix_raw, escpos_thermal
from app.printing.base import BillRenderData, KotTicketRenderData

logger = logging.getLogger("kotmate.printing")


def dispatch_bill_print(printer: Printer, bill: BillRenderData) -> bytes:
    """Renders and logs the print job — actual transport is the caller's job
    (bill_service._dispatch_print_for_bill): `usb`/`local_agent`/`bluetooth` printers
    are physically attached to (or paired with) the counter machine's browser, not this
    container, so those bytes go back to the frontend over WebUSB/local-agent/Web
    Bluetooth instead; `network`/`wifi` printers are reachable directly from here via
    `printing.network_transport`.
    """
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
    return content if isinstance(content, bytes) else content.encode("utf-8")


def dispatch_test_print(printer_type: str, paper_width_mm: int | None) -> bytes:
    if printer_type == "thermal":
        return escpos_thermal.render_test_print(paper_width_mm)
    return dotmatrix_raw.render_test_print(paper_width_mm).encode("utf-8")


def dispatch_kot_print(printer: Printer, ticket: KotTicketRenderData) -> bytes:
    """Renders and logs the print job — mirrors `dispatch_bill_print` above, including
    returning the same bytes for `usb`/`local_agent` printers so the caller can hand
    them to the frontend for local delivery instead of a server-side transport.
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
    return content if isinstance(content, bytes) else content.encode("utf-8")
