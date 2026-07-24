from pydantic import BaseModel


class PlanMixOut(BaseModel):
    plan_code: str
    plan_name: str
    tenant_count: int


class PlatformDashboardOut(BaseModel):
    active_tenant_count: int
    trialing_count: int
    churned_this_month_count: int
    mrr_paise: int
    plan_mix: list[PlanMixOut]
    overdue_invoices_count: int
