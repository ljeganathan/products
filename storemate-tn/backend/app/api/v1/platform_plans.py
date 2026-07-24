import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.middleware.rbac import require_role
from app.models.enums import UserRole
from app.models.plan import Plan
from app.repositories.plan_repository import PlanRepository
from app.schemas.platform_plan import PlanCreate, PlanOut, PlanUpdate

router = APIRouter(prefix="/platform/plans", tags=["platform"])

require_owner = require_role(UserRole.PRODUCT_OWNER)


@router.get("", response_model=list[PlanOut])
async def list_plans(
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> list[PlanOut]:
    plans = await PlanRepository(db).list_all()
    return [PlanOut.model_validate(p) for p in plans]


@router.post("", response_model=PlanOut, status_code=status.HTTP_201_CREATED)
async def create_plan(
    payload: PlanCreate,
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> PlanOut:
    repo = PlanRepository(db)
    if await repo.get_by_code(payload.code) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A plan with code '{payload.code.value}' already exists",
        )
    plan = await repo.create(Plan(**payload.model_dump()))
    await db.commit()
    return PlanOut.model_validate(plan)


@router.patch("/{plan_id}", response_model=PlanOut)
async def update_plan(
    plan_id: uuid.UUID,
    payload: PlanUpdate,
    _: object = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> PlanOut:
    repo = PlanRepository(db)
    plan = await repo.get_by_id(plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)

    await db.flush()
    await db.commit()
    return PlanOut.model_validate(plan)
