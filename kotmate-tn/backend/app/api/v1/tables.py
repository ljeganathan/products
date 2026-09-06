import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.schemas.guest import TableQrCodeResponse
from app.schemas.tables import TableCreateRequest, TableResponse, TableUpdateRequest
from app.services.guest_service import get_or_create_qr_code_for_table, get_qr_code_for_table
from app.services.table_service import (
    compute_occupied_table_ids,
    create_table,
    get_table_or_404,
    list_tables,
    update_table,
)
from app.services.tenant_onboarding import get_active_plan

# Read access is broad (Phase 07 POS needs it for the table selector/floor plan);
# writes are tenant_admin-only, enforced per-route below.
router = APIRouter(prefix="/tables", tags=["tables"], dependencies=[Depends(require_tenant_scope)])

_QR_UPGRADE_MESSAGE = "QR self-order is only available on Pro Max. Upgrade to unlock it."


async def _require_qr_feature(db: AsyncSession, tenant_id: uuid.UUID) -> None:
    plan = await get_active_plan(db, tenant_id)
    if not plan or not plan.features.get("qr_self_order"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, _QR_UPGRADE_MESSAGE)


def _qr_response(row, table_number: str) -> TableQrCodeResponse:
    return TableQrCodeResponse(
        id=row.id,
        table_id=row.table_id,
        table_number=table_number,
        qr_token=row.qr_token,
        is_active=row.is_active,
    )


def _with_computed_status(table, occupied_ids: set[uuid.UUID]) -> TableResponse:
    return TableResponse.model_validate(table).model_copy(
        update={"status": "occupied" if table.id in occupied_ids else "free"}
    )


@router.get("", response_model=list[TableResponse])
async def list_tenant_tables(
    location_id: uuid.UUID | None = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[TableResponse]:
    tables = await list_tables(db, current_user.tenant_id, location_id)
    occupied_ids = await compute_occupied_table_ids(db, current_user.tenant_id, [t.id for t in tables])
    return [_with_computed_status(t, occupied_ids) for t in tables]


@router.post(
    "", response_model=TableResponse, status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def create_tenant_table(
    payload: TableCreateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TableResponse:
    try:
        table = await create_table(db, current_user.tenant_id, payload)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That table number is already in use at this location"
        ) from exc
    return _with_computed_status(table, set())


@router.patch(
    "/{table_id}", response_model=TableResponse, dependencies=[Depends(require_role("tenant_admin"))]
)
async def update_tenant_table(
    table_id: uuid.UUID,
    payload: TableUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TableResponse:
    table = await get_table_or_404(db, current_user.tenant_id, table_id)
    try:
        table = await update_table(db, current_user.tenant_id, table, payload)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That table number is already in use at this location"
        ) from exc
    occupied_ids = await compute_occupied_table_ids(db, current_user.tenant_id, [table.id])
    return _with_computed_status(table, occupied_ids)


@router.post(
    "/{table_id}/qr-code",
    response_model=TableQrCodeResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def generate_table_qr_code(
    table_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TableQrCodeResponse:
    """One QR per table (production feedback: a separate physical code per seat isn't
    maintainable) — idempotent, safe to call again; a table only ever gets one code.
    """
    await _require_qr_feature(db, current_user.tenant_id)
    table = await get_table_or_404(db, current_user.tenant_id, table_id)
    qr = await get_or_create_qr_code_for_table(db, current_user.tenant_id, table)
    await db.commit()
    return _qr_response(qr, table.table_number)


@router.get(
    "/{table_id}/qr-code",
    response_model=TableQrCodeResponse | None,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def get_table_qr_code(
    table_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TableQrCodeResponse | None:
    await _require_qr_feature(db, current_user.tenant_id)
    table = await get_table_or_404(db, current_user.tenant_id, table_id)
    qr = await get_qr_code_for_table(db, current_user.tenant_id, table_id)
    return _qr_response(qr, table.table_number) if qr else None
