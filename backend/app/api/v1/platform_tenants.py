import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.core.security import hash_password
from app.middleware.rbac import require_role
from app.models.enums import SubscriptionStatus, TenantStatus, UserRole
from app.models.store import Store
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.models.user import User
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.tenant_repository import TenantRepository
from app.repositories.user_repository import UserRepository
from app.schemas.common import PaginatedResponse
from app.schemas.platform_tenant import TenantCreate, TenantOut, TenantUpdate
from app.services.subscription_service import BILLING_PERIOD_DAYS, build_tenant_out

router = APIRouter(prefix="/platform/tenants", tags=["platform"])

require_owner = require_role(UserRole.PRODUCT_OWNER)


@router.get("", response_model=PaginatedResponse[TenantOut])
async def list_tenants(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    status_filter: TenantStatus | None = Query(None, alias="status"),
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[TenantOut]:
    repo = TenantRepository(db)
    tenants, total = await repo.list_all(
        page=page, page_size=page_size, search=search, status=status_filter
    )
    return PaginatedResponse(
        items=[await build_tenant_out(db, t) for t in tenants],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    payload: TenantCreate,
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> TenantOut:
    tenant_repo = TenantRepository(db)
    if await tenant_repo.get_by_owner_email(payload.owner_email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A tenant with this owner email already exists",
        )

    user_repo = UserRepository(db)
    if await user_repo.get_by_email(payload.admin_email) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    plan = await PlanRepository(db).get_by_code(payload.plan_code)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown plan code '{payload.plan_code.value}'",
        )

    tenant = await tenant_repo.create(
        Tenant(
            name=payload.name,
            owner_email=payload.owner_email,
            owner_phone=payload.owner_phone,
            status=TenantStatus.ACTIVE,
        )
    )

    store = Store(
        tenant_id=tenant.id,
        name=payload.store_name or f"{payload.name} - Main",
        is_default=True,
    )
    db.add(store)
    await db.flush()

    now = datetime.now(UTC)
    await SubscriptionRepository(db).create(
        Subscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=now,
            current_period_end=now + timedelta(days=BILLING_PERIOD_DAYS),
        )
    )

    admin = User(
        tenant_id=tenant.id,
        store_id=store.id,
        name=payload.admin_name,
        email=payload.admin_email,
        password_hash=hash_password(payload.admin_password),
        role=UserRole.ADMIN,
    )
    db.add(admin)
    await db.flush()

    result = await build_tenant_out(db, tenant)
    await db.commit()
    return result


@router.get("/{tenant_id}", response_model=TenantOut)
async def get_tenant(
    tenant_id: uuid.UUID,
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> TenantOut:
    tenant = await TenantRepository(db).get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return await build_tenant_out(db, tenant)


@router.patch("/{tenant_id}", response_model=TenantOut)
async def update_tenant(
    tenant_id: uuid.UUID,
    payload: TenantUpdate,
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> TenantOut:
    tenant = await TenantRepository(db).get_by_id(tenant_id)
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    tenant.status = payload.status
    await db.flush()
    result = await build_tenant_out(db, tenant)
    await db.commit()
    return result
