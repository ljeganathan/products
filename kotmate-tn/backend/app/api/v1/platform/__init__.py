from fastapi import APIRouter, Depends

from app.api.v1.platform.metrics import router as metrics_router
from app.api.v1.platform.plans import router as plans_router
from app.api.v1.platform.settings import router as settings_router
from app.api.v1.platform.tenants import router as tenants_router
from app.core.deps import require_platform_scope

# Every route under /platform is product_owner-only (CLAUDE.md §5) — enforced once
# here rather than per-route, so a new route added later can't accidentally forget it.
router = APIRouter(prefix="/platform", dependencies=[Depends(require_platform_scope)])
router.include_router(tenants_router)
router.include_router(plans_router)
router.include_router(settings_router)
router.include_router(metrics_router)
