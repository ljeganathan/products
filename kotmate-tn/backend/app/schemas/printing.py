import uuid

from pydantic import BaseModel


class PrintJobPayload(BaseModel):
    """Raw ESC/POS (or dot-matrix) bytes for a `usb`/`local_agent` printer the backend
    cannot reach itself — that printer is physically attached to whichever machine's
    browser is running the POS/KOT screen, not to the backend container, so the browser
    has to forward these bytes to a local print-agent or WebUSB (lib/printDispatch.ts).
    Shared by bill (schemas/bills.py) and KOT ticket (schemas/kot.py) responses.
    """

    printer_id: uuid.UUID
    connection_type: str
    connection_details: dict
    data_base64: str
