import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models import Plan
from app.schemas.platform import PlanResponse, PlanUpdateRequest

router = APIRouter(prefix="/plans", tags=["platform-plans"])


@router.get("", response_model=list[PlanResponse])
async def list_plans(db: AsyncSession = Depends(get_db)) -> list[Plan]:
    return (await db.execute(select(Plan).order_by(Plan.price_monthly))).scalars().all()


@router.patch("/{plan_id}", response_model=PlanResponse)
async def update_plan(
    plan_id: uuid.UUID, payload: PlanUpdateRequest, db: AsyncSession = Depends(get_db)
) -> Plan:
    plan = (await db.execute(select(Plan).where(Plan.id == plan_id))).scalar_one_or_none()
    if plan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plan, field, value)
    await db.commit()
    return plan
