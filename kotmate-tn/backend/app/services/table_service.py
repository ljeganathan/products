import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SeatingSection, Table, TenantLocation
from app.schemas.tables import TableCreateRequest, TableUpdateRequest


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


async def _validate_seating_section(
    session: AsyncSession, tenant_id: uuid.UUID, section_id: uuid.UUID
) -> None:
    section = (
        await session.execute(
            select(SeatingSection).where(
                SeatingSection.id == section_id, SeatingSection.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if section is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "section_id does not belong to this tenant")
    if not section.is_seating:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"'{section.name_en}' is a non-seating section (e.g. Takeaway) and cannot be assigned to a table",
        )


async def list_tables(
    session: AsyncSession, tenant_id: uuid.UUID, location_id: uuid.UUID | None
) -> list[Table]:
    query = select(Table).where(Table.tenant_id == tenant_id)
    if location_id is not None:
        query = query.where(Table.location_id == location_id)
    rows = await session.execute(query.order_by(Table.table_number))
    return list(rows.scalars().all())


async def get_table_or_404(session: AsyncSession, tenant_id: uuid.UUID, table_id: uuid.UUID) -> Table:
    table = (
        await session.execute(select(Table).where(Table.id == table_id, Table.tenant_id == tenant_id))
    ).scalar_one_or_none()
    if table is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Table not found")
    return table


async def create_table(session: AsyncSession, tenant_id: uuid.UUID, req: TableCreateRequest) -> Table:
    await _validate_location(session, tenant_id, req.location_id)
    await _validate_seating_section(session, tenant_id, req.section_id)

    table = Table(
        tenant_id=tenant_id,
        location_id=req.location_id,
        section_id=req.section_id,
        table_number=req.table_number,
        seating_capacity=req.seating_capacity,
        status="free",
        is_active=True,
    )
    session.add(table)
    await session.flush()
    return table


async def update_table(
    session: AsyncSession, tenant_id: uuid.UUID, table: Table, req: TableUpdateRequest
) -> Table:
    data = req.model_dump(exclude_unset=True)
    if "location_id" in data:
        await _validate_location(session, tenant_id, data["location_id"])
    if "section_id" in data:
        await _validate_seating_section(session, tenant_id, data["section_id"])

    for field, value in data.items():
        setattr(table, field, value)

    await session.flush()
    return table
