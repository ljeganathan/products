import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.schemas.guest import SectionQrCodeResponse
from app.schemas.sections import (
    SectionCreateRequest,
    SectionReorderRequest,
    SectionResponse,
    SectionUpdateRequest,
)
from app.services.guest_service import get_or_create_qr_code_for_section, get_qr_code_for_section
from app.services.section_service import (
    create_section,
    get_section_or_404,
    list_active_sections,
    list_sections,
    reorder_sections,
    update_section,
)
from app.services.tenant_onboarding import get_active_plan

# Read access is broad (Phase 07/08/09 all need seating sections for the POS table
# selector, KOT ticket display, and section-aware pricing/tax); writes are
# tenant_admin-only, enforced per-route below.
router = APIRouter(prefix="/sections", tags=["sections"], dependencies=[Depends(require_tenant_scope)])

_QR_UPGRADE_MESSAGE = "QR self-order is only available on Pro Max. Upgrade to unlock it."


async def _require_qr_feature(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    plan = await get_active_plan(db, tenant_id)
    if not plan or not plan.features.get("qr_self_order"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, _QR_UPGRADE_MESSAGE)


def _qr_response(row, section_name_en: str) -> SectionQrCodeResponse:
    return SectionQrCodeResponse(
        id=row.id,
        section_id=row.section_id,
        section_name_en=section_name_en,
        qr_token=row.qr_token,
        is_active=row.is_active,
    )


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


@router.post(
    "/{section_id}/qr-code",
    response_model=SectionQrCodeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def generate_section_qr_code(
    section_id: uuid.UUID,
    location_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SectionQrCodeResponse:
    """A Takeaway/Online Delivery section's QR (Phase 26) — one per (location,
    section), idempotent, safe to call again. `location_id` is a required query param
    rather than inferred from the section: `seating_sections` is tenant-wide (a
    multi-location tenant's one "Takeaway" section is shared by every branch), so the
    admin picks which branch this particular printed code is for.
    """
    await _require_qr_feature(db, current_user.tenant_id)
    section = await get_section_or_404(db, current_user.tenant_id, section_id)
    qr = await get_or_create_qr_code_for_section(db, current_user.tenant_id, section, location_id)
    await db.commit()
    return _qr_response(qr, section.name_en)


@router.get(
    "/{section_id}/qr-code",
    response_model=SectionQrCodeResponse | None,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def get_section_qr_code(
    section_id: uuid.UUID,
    location_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SectionQrCodeResponse | None:
    await _require_qr_feature(db, current_user.tenant_id)
    section = await get_section_or_404(db, current_user.tenant_id, section_id)
    qr = await get_qr_code_for_section(db, current_user.tenant_id, section_id, location_id)
    return _qr_response(qr, section.name_en) if qr else None
