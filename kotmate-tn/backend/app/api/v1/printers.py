import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.schemas.printers import PrinterCreateRequest, PrinterResponse, PrinterUpdateRequest
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
