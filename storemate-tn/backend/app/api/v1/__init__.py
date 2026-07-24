from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.bills import router as bills_router
from app.api.v1.categories import router as categories_router
from app.api.v1.company_settings import router as company_settings_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.discount_rules import router as discount_rules_router
from app.api.v1.health import router as health_router
from app.api.v1.items import router as items_router
from app.api.v1.language_settings import router as language_settings_router
from app.api.v1.notifications import router as notifications_router
from app.api.v1.platform_dashboard import router as platform_dashboard_router
from app.api.v1.platform_invoices import router as platform_invoices_router
from app.api.v1.platform_plans import router as platform_plans_router
from app.api.v1.platform_settings import router as platform_settings_router
from app.api.v1.platform_subscriptions import router as platform_subscriptions_router
from app.api.v1.platform_tenants import router as platform_tenants_router
from app.api.v1.pos import router as pos_router
from app.api.v1.printer_profiles import router as printer_profiles_router
from app.api.v1.reports import router as reports_router
from app.api.v1.stock import router as stock_router
from app.api.v1.subscription import router as subscription_router
from app.api.v1.tax_profiles import router as tax_profiles_router
from app.api.v1.users import router as users_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(categories_router)
api_router.include_router(items_router)
api_router.include_router(stock_router)
api_router.include_router(tax_profiles_router)
api_router.include_router(company_settings_router)
api_router.include_router(printer_profiles_router)
api_router.include_router(pos_router)
api_router.include_router(bills_router)
api_router.include_router(discount_rules_router)
api_router.include_router(notifications_router)
api_router.include_router(language_settings_router)
api_router.include_router(subscription_router)
api_router.include_router(platform_tenants_router)
api_router.include_router(platform_plans_router)
api_router.include_router(platform_subscriptions_router)
api_router.include_router(platform_invoices_router)
api_router.include_router(platform_settings_router)
api_router.include_router(dashboard_router)
api_router.include_router(platform_dashboard_router)
api_router.include_router(reports_router)
