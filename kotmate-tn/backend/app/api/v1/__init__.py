from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.bills import router as bills_router
from app.api.v1.categories import router as categories_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.discount_rules import router as discount_rules_router
from app.api.v1.health import router as health_router
from app.api.v1.items import router as items_router
from app.api.v1.kot import router as kot_router
from app.api.v1.locations import router as locations_router
from app.api.v1.orders import router as orders_router
from app.api.v1.platform import router as platform_router
from app.api.v1.printers import router as printers_router
from app.api.v1.reports import router as reports_router
from app.api.v1.sections import router as sections_router
from app.api.v1.settings import router as settings_router
from app.api.v1.tables import router as tables_router
from app.api.v1.tax_rules import router as tax_rules_router
from app.api.v1.users import router as users_router
from app.api.v1.waiters import router as waiters_router

# Public-route allowlist (CLAUDE.md §2/Phase 02 acceptance criteria: every route from
# Phase 01 onward requires auth by default). Only these three are unauthenticated:
#   GET  /api/v1/health
#   POST /api/v1/auth/login
#   POST /api/v1/auth/refresh
# Every other route on every future router MUST depend on one of
# app.core.deps.get_current_user / require_role / require_tenant_scope /
# require_platform_scope, e.g. via `include_router(..., dependencies=[Depends(...)])`.
api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(platform_router)
api_router.include_router(users_router)
api_router.include_router(categories_router)
api_router.include_router(items_router)
api_router.include_router(locations_router)
api_router.include_router(waiters_router)
api_router.include_router(sections_router)
api_router.include_router(tables_router)
api_router.include_router(orders_router)
api_router.include_router(kot_router)
api_router.include_router(printers_router)
api_router.include_router(tax_rules_router)
api_router.include_router(discount_rules_router)
api_router.include_router(bills_router)
api_router.include_router(settings_router)
api_router.include_router(reports_router)
api_router.include_router(dashboard_router)
