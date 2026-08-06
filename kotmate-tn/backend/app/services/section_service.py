import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SeatingSection
from app.schemas.sections import SectionCreateRequest, SectionReorderRequest, SectionUpdateRequest


async def list_sections(session: AsyncSession, tenant_id: uuid.UUID) -> list[SeatingSection]:
    rows = await session.execute(
        select(SeatingSection)
        .where(SeatingSection.tenant_id == tenant_id)
        .order_by(SeatingSection.display_order)
    )
    return list(rows.scalars().all())


async def list_active_sections(session: AsyncSession, tenant_id: uuid.UUID) -> list[SeatingSection]:
    """Active sections only — the POS table/section picker (Phase 07); includes both
    `is_seating` (table required) and non-seating (Takeaway/Online Delivery, no table).
    """
    rows = await session.execute(
        select(SeatingSection)
        .where(SeatingSection.tenant_id == tenant_id, SeatingSection.is_active.is_(True))
        .order_by(SeatingSection.display_order)
    )
    return list(rows.scalars().all())


async def get_section_or_404(
    session: AsyncSession, tenant_id: uuid.UUID, section_id: uuid.UUID
) -> SeatingSection:
    section = (
        await session.execute(
            select(SeatingSection).where(
                SeatingSection.id == section_id, SeatingSection.tenant_id == tenant_id
            )
        )
    ).scalar_one_or_none()
    if section is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Seating section not found")
    return section


async def create_section(
    session: AsyncSession, tenant_id: uuid.UUID, req: SectionCreateRequest
) -> SeatingSection:
    display_order = req.display_order
    if display_order is None:
        max_order = (
            await session.execute(
                select(func.max(SeatingSection.display_order)).where(SeatingSection.tenant_id == tenant_id)
            )
        ).scalar_one()
        display_order = (max_order + 1) if max_order is not None else 0

    section = SeatingSection(
        tenant_id=tenant_id,
        name_en=req.name_en,
        name_ta=req.name_ta,
        is_seating=req.is_seating,
        display_order=display_order,
        is_active=True,
    )
    session.add(section)
    await session.flush()
    return section


async def update_section(
    session: AsyncSession, section: SeatingSection, req: SectionUpdateRequest
) -> SeatingSection:
    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(section, field, value)
    await session.flush()
    return section


async def reorder_sections(
    session: AsyncSession, tenant_id: uuid.UUID, req: SectionReorderRequest
) -> list[SeatingSection]:
    ids = [entry.id for entry in req.sections]
    existing = (
        await session.execute(
            select(SeatingSection.id).where(
                SeatingSection.tenant_id == tenant_id, SeatingSection.id.in_(ids)
            )
        )
    ).scalars().all()
    if set(existing) != set(ids):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "One or more sections do not belong to this tenant"
        )

    order_by_id = {entry.id: entry.display_order for entry in req.sections}
    sections = await list_sections(session, tenant_id)
    for section in sections:
        if section.id in order_by_id:
            section.display_order = order_by_id[section.id]
    await session.flush()
    return await list_sections(session, tenant_id)
