import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HotelMaster, TenantLocation


@dataclass
class BranchHeader:
    name: str
    address_lines: list[str]
    gstin: str | None


async def resolve_branch_header(session: AsyncSession, location_id: uuid.UUID) -> BranchHeader:
    """Name/address/GSTIN for whichever location a print job's printer belongs to — one
    printer always belongs to exactly one location, so this is the "branch identity" any
    print output (bill, KOT, and now report headers — CLAUDE.md §10/§11) shows. Falls
    back to the bare `tenant_locations.name` when no Hotel Master has been filled in yet
    for that location, so printing never breaks before Settings > Hotel Master is set up.
    """
    hotel = (
        await session.execute(select(HotelMaster).where(HotelMaster.location_id == location_id))
    ).scalar_one_or_none()
    location = (
        await session.execute(select(TenantLocation).where(TenantLocation.id == location_id))
    ).scalar_one()

    name = hotel.name if hotel else location.name
    # Door No./Street/City/Pincode on one line, phone on its own line below — both
    # centered by the thermal adapter; district is dropped as redundant with city for a
    # single-location context, phone gets its own more-prominent line.
    address_parts = (
        [p for p in [hotel.door_no, hotel.street, hotel.city, hotel.pincode] if p] if hotel else []
    )
    address_lines = [", ".join(address_parts)] if address_parts else []
    if hotel and hotel.phone:
        address_lines.append(f"Ph: {hotel.phone}")

    return BranchHeader(name=name, address_lines=address_lines, gstin=hotel.gstin if hotel else None)
