import base64
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.printing.dispatcher import dispatch_test_print
from app.printing.network_transport import send_raw_bytes_over_network
from app.schemas.printers import (
    PrinterCreateRequest,
    PrinterResponse,
    PrinterTestPrintRequest,
    PrinterTestPrintResponse,
    PrinterUpdateRequest,
)
from app.schemas.printing import PrintJobPayload
from app.services.printer_service import create_printer, get_printer_or_404, list_printers, update_printer

# Registering/editing printers is tenant_admin-only (Settings, Phase 08 stub — full
# Settings page in Phase 10); reads are broad since Phase 09 billing will also need to
# look up the bill printer for a location.
router = APIRouter(
    prefix="/printers", tags=["printers"], dependencies=[Depends(require_tenant_scope)]
)


@router.get("", response_model=list[PrinterResponse])
async def list_tenant_printers(
    location_id: uuid.UUID | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PrinterResponse]:
    printers = await list_printers(db, current_user.tenant_id, location_id)
    return [PrinterResponse.model_validate(p) for p in printers]


@router.post(
    "",
    response_model=PrinterResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def create_tenant_printer(
    payload: PrinterCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PrinterResponse:
    printer = await create_printer(db, current_user.tenant_id, payload)
    await db.commit()
    return PrinterResponse.model_validate(printer)


@router.post(
    "/test-print",
    response_model=PrinterTestPrintResponse,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def test_print_printer(payload: PrinterTestPrintRequest) -> PrinterTestPrintResponse:
    """Renders and sends a short test ticket using exactly the connection details
    currently in the Add/Edit Printer form — works before the printer is even saved, so
    a cashier can confirm the connection before committing it (CLAUDE.md §10).
    """
    content = dispatch_test_print(payload.printer_type, payload.paper_width_mm)

    if payload.connection_type in ("usb", "local_agent", "bluetooth"):
        # Physically attached to (or paired with) whichever machine's browser has this
        # settings page open, not this backend container — hand the bytes back for the
        # frontend to dispatch via WebUSB/local-agent/Web Bluetooth
        # (lib/printDispatch.ts), same as a real bill.
        return PrinterTestPrintResponse(
            printed=False,
            print_job=PrintJobPayload(
                printer_id=uuid.uuid4(),
                connection_type=payload.connection_type,
                connection_details=payload.connection_details,
                data_base64=base64.b64encode(content).decode("ascii"),
            ),
        )

    if payload.connection_type in ("network", "wifi"):
        error = send_raw_bytes_over_network(
            payload.connection_details.get("ip_address"), payload.connection_details.get("port"), content
        )
        if error:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, error)
        return PrinterTestPrintResponse(printed=True, print_job=None)

    raise HTTPException(
        status.HTTP_400_BAD_REQUEST,
        f"{payload.connection_type.replace('_', ' ').title()} printing isn't supported yet.",
    )


@router.patch(
    "/{printer_id}", response_model=PrinterResponse, dependencies=[Depends(require_role("tenant_admin"))]
)
async def update_tenant_printer(
    printer_id: uuid.UUID,
    payload: PrinterUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PrinterResponse:
    printer = await get_printer_or_404(db, current_user.tenant_id, printer_id)
    printer = await update_printer(db, current_user.tenant_id, printer, payload)
    await db.commit()
    return PrinterResponse.model_validate(printer)
