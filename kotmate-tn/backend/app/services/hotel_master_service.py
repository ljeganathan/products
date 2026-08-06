import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.constants import GST_STATE_CODES
from app.models import HotelMaster, Tenant, TenantLocation
from app.schemas.hotel_master import HotelMasterResponse, HotelMasterUpdateRequest
from app.services.storage import get_storage

_ALLOWED_LOGO_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


def gstin_state_warning(gstin: str | None, state: str | None) -> str | None:
    """Pure function: derives the state a GSTIN's first two digits imply and compares
    it against the selected state — a mismatch is surfaced as a warning, never a hard
    validation failure, since data entry order varies (CLAUDE.md Phase 10 acceptance
    criteria).
    """
    if not gstin or not state:
        return None
    expected_state = GST_STATE_CODES.get(gstin[:2])
    if expected_state is None:
        return f"GSTIN prefix '{gstin[:2]}' isn't a recognized state/UT code — double-check the GSTIN."
    if expected_state != state:
        return f"This GSTIN's state code suggests {expected_state}, but {state} is selected."
    return None


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


async def get_hotel_master_row(
    session: AsyncSession, tenant_id: uuid.UUID, location_id: uuid.UUID
) -> HotelMaster | None:
    return (
        await session.execute(
            select(HotelMaster).where(
                HotelMaster.tenant_id == tenant_id, HotelMaster.location_id == location_id
            )
        )
    ).scalar_one_or_none()


def _build_response(row: HotelMaster | None, location_id: uuid.UUID) -> HotelMasterResponse:
    if row is None:
        return HotelMasterResponse(location_id=location_id)
    return HotelMasterResponse(
        id=row.id,
        location_id=row.location_id,
        name=row.name,
        door_no=row.door_no,
        street=row.street,
        city=row.city,
        district=row.district,
        state=row.state,
        pincode=row.pincode,
        phone=row.phone,
        gstin=row.gstin,
        logo_url=row.logo_url,
        upi_id=row.upi_id,
        show_tamil_names=row.show_tamil_names,
        gstin_state_warning=gstin_state_warning(row.gstin, row.state),
        created_at=row.created_at,
    )


async def get_hotel_master(
    session: AsyncSession, tenant_id: uuid.UUID, location_id: uuid.UUID
) -> HotelMasterResponse:
    """Never 404s — a location without a saved Hotel Master yet just returns an empty
    shell so the Settings form has something to render before the first save.
    """
    await _validate_location(session, tenant_id, location_id)
    row = await get_hotel_master_row(session, tenant_id, location_id)
    return _build_response(row, location_id)


async def upsert_hotel_master(
    session: AsyncSession, tenant_id: uuid.UUID, req: HotelMasterUpdateRequest
) -> HotelMasterResponse:
    await _validate_location(session, tenant_id, req.location_id)
    row = await get_hotel_master_row(session, tenant_id, req.location_id)
    if row is None:
        row = HotelMaster(tenant_id=tenant_id, location_id=req.location_id)
        session.add(row)

    row.name = req.name
    row.door_no = req.door_no
    row.street = req.street
    row.city = req.city
    row.district = req.district
    row.state = req.state
    row.pincode = req.pincode
    row.phone = req.phone
    row.gstin = req.gstin
    row.upi_id = req.upi_id
    row.show_tamil_names = req.show_tamil_names

    await session.flush()
    return _build_response(row, req.location_id)


async def upload_hotel_master_logo(
    session: AsyncSession, tenant: Tenant, location_id: uuid.UUID, file: UploadFile
) -> HotelMasterResponse:
    await _validate_location(session, tenant.id, location_id)
    if file.content_type not in _ALLOWED_LOGO_CONTENT_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only JPEG, PNG, or WebP images are allowed")

    content = await file.read()
    if len(content) > get_settings().MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Image exceeds the maximum upload size")

    row = await get_hotel_master_row(session, tenant.id, location_id)
    if row is None:
        # A logo can be the very first thing an admin uploads before filling in the
        # rest of the form — `name` defaults to the location's own name so the row is
        # still valid (NOT NULL) until the admin saves proper Hotel Master details.
        location = (
            await session.execute(select(TenantLocation).where(TenantLocation.id == location_id))
        ).scalar_one()
        row = HotelMaster(tenant_id=tenant.id, location_id=location_id, name=location.name)
        session.add(row)
        await session.flush()

    storage = get_storage()
    url = await storage.save(
        tenant_id=tenant.id, subfolder="hotel", filename=file.filename or "logo", content=content
    )
    row.logo_url = url
    await session.flush()
    return _build_response(row, location_id)
