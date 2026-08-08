import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Printer, TenantLocation
from app.schemas.printers import PrinterCreateRequest, PrinterUpdateRequest


async def _validate_location(session: AsyncSession, tenant_id: uuid.UUID, location_id: uuid.UUID) -> None:
    exists = (
        await session.execute(
            select(TenantLocation.id).where(
                TenantLocation.id == location_id, TenantLocation.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "location_id does not belong to this tenant")


async def list_printers(
    session: AsyncSession, tenant_id: uuid.UUID, location_id: uuid.UUID | None
) -> list[Printer]:
    query = select(Printer).where(Printer.tenant_id == tenant_id)
    if location_id is not None:
        query = query.where(Printer.location_id == location_id)
    rows = await session.execute(query.order_by(Printer.name))
    return list(rows.scalars().all())


async def get_printer_or_404(session: AsyncSession, tenant_id: uuid.UUID, printer_id: uuid.UUID) -> Printer:
    printer = (
        await session.execute(
            select(Printer).where(Printer.id == printer_id, Printer.tenant_id == tenant_id)
        )
    ).scalar_one_or_none()
    if printer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Printer not found")
    return printer


async def create_printer(session: AsyncSession, tenant_id: uuid.UUID, req: PrinterCreateRequest) -> Printer:
    await _validate_location(session, tenant_id, req.location_id)
    printer = Printer(
        tenant_id=tenant_id,
        location_id=req.location_id,
        name=req.name,
        target=req.target,
        printer_type=req.printer_type,
        connection_type=req.connection_type,
        connection_details=req.connection_details,
        paper_width_mm=req.paper_width_mm,
        is_active=True,
    )
    session.add(printer)
    await session.flush()
    return printer


async def update_printer(
    session: AsyncSession, tenant_id: uuid.UUID, printer: Printer, req: PrinterUpdateRequest
) -> Printer:
    data = req.model_dump(exclude_unset=True)
    if "location_id" in data:
        await _validate_location(session, tenant_id, data["location_id"])
    for field, value in data.items():
        setattr(printer, field, value)
    await session.flush()
    return printer
