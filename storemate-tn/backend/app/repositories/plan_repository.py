import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import PlanCode
from app.models.plan import Plan


class PlanRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, plan_id: uuid.UUID) -> Plan | None:
        return await self.db.scalar(select(Plan).where(Plan.id == plan_id))

    async def get_by_code(self, code: PlanCode) -> Plan | None:
        return await self.db.scalar(select(Plan).where(Plan.code == code))

    async def list_all(self) -> list[Plan]:
        result = await self.db.execute(select(Plan).order_by(Plan.price_paise))
        return list(result.scalars().all())

    async def create(self, plan: Plan) -> Plan:
        self.db.add(plan)
        await self.db.flush()
        return plan
