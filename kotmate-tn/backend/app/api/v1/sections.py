import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.schemas.sections import (
    SectionCreateRequest,
    SectionReorderRequest,
    SectionResponse,
    SectionUpdateRequest,
)
from app.services.section_service import (
    create_section,
    get_section_or_404,
    list_active_sections,
    list_sections,
    reorder_sections,
    update_section,
)

# Read access is broad (Phase 07/08/09 all need seating sections for the POS table
# selector, KOT ticket display, and section-aware pricing/tax); writes are
# tenant_admin-only, enforced per-route below.
router = APIRouter(prefix="/sections", tags=["sections"], dependencies=[Depends(require_tenant_scope)])


@router.get("", response_model=list[SectionResponse])
async def list_tenant_sections(
    current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[SectionResponse]:
    sections = await list_sections(db, current_user.tenant_id)
    return [SectionResponse.model_validate(s) for s in sections]


@router.get("/pos", response_model=list[SectionResponse])
async def list_pos_sections(
    current_user: CurrentUser = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> list[SectionResponse]:
    sections = await list_active_sections(db, current_user.tenant_id)
    return [SectionResponse.model_validate(s) for s in sections]


@router.post(
    "", response_model=SectionResponse, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def create_tenant_section(
    payload: SectionCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SectionResponse:
    section = await create_section(db, current_user.tenant_id, payload)
    await db.commit()
    return SectionResponse.model_validate(section)


@router.patch(
    "/{section_id}", response_model=SectionResponse, dependencies=[Depends(require_role("tenant_admin"))]
)
async def update_tenant_section(
    section_id: uuid.UUID,
    payload: SectionUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SectionResponse:
    section = await get_section_or_404(db, current_user.tenant_id, section_id)
    section = await update_section(db, section, payload)
    await db.commit()
    return SectionResponse.model_validate(section)


@router.put(
    "/reorder", response_model=list[SectionResponse], dependencies=[Depends(require_role("tenant_admin"))]
)
async def reorder_tenant_sections(
    payload: SectionReorderRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SectionResponse]:
    sections = await reorder_sections(db, current_user.tenant_id, payload)
    await db.commit()
    return [SectionResponse.model_validate(s) for s in sections]
