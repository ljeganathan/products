import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_user, require_role, require_tenant_scope
from app.db.session import get_db
from app.models import Tenant
from app.schemas.category_display import CategoryDisplaySettingsRequest, CategoryDisplaySettingsResponse
from app.schemas.hotel_master import HotelMasterResponse, HotelMasterUpdateRequest
from app.schemas.pos_layout import (
    PosLayoutSettingsRequest,
    PosLayoutSettingsResponse,
    WaiterMandatorySettingsRequest,
    WaiterMandatorySettingsResponse,
)
from app.schemas.pos_preferences import DefaultPaymentMethodRequest, DefaultPaymentMethodResponse
from app.schemas.report_print import (
    ReportPrintingSettingsRequest,
    ReportPrintingSettingsResponse,
    ReportTamilNamesSettingsRequest,
    ReportTamilNamesSettingsResponse,
)
from app.schemas.stock import StockManagementSettingsRequest, StockManagementSettingsResponse
from app.services.hotel_master_service import (
    get_hotel_master,
    remove_hotel_master_logo,
    upload_hotel_master_logo,
    upsert_hotel_master,
)
from app.services.report_print_service import has_report_printing_feature
from app.services.stock_service import has_stock_management_feature
from app.services.tenant_onboarding import get_active_plan

# Hotel Master (Phase 10) — tenant_admin-only writes; reads broad since a future
# customer-facing bill-preview screen or another staff role could reasonably need to
# see the same info this form edits.
router = APIRouter(prefix="/settings", tags=["settings"], dependencies=[Depends(require_tenant_scope)])


async def _get_tenant(db: AsyncSession, current_user: CurrentUser) -> Tenant:
    return (await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))).scalar_one()


@router.get("/hotel-master", response_model=HotelMasterResponse)
async def get_tenant_hotel_master(
    location_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HotelMasterResponse:
    return await get_hotel_master(db, current_user.tenant_id, location_id)


@router.put(
    "/hotel-master", response_model=HotelMasterResponse, dependencies=[Depends(require_role("tenant_admin"))]
)
async def upsert_tenant_hotel_master(
    payload: HotelMasterUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HotelMasterResponse:
    result = await upsert_hotel_master(db, current_user.tenant_id, payload)
    await db.commit()
    return result


@router.patch(
    "/stock-management",
    response_model=StockManagementSettingsResponse,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def update_stock_management_setting(
    payload: StockManagementSettingsRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> StockManagementSettingsResponse:
    """The tenant-level kill switch (Pro/Pro Max only) — soft-disable, never touches
    items.track_inventory/available_qty, so re-enabling restores prior config exactly.
    """
    plan = await get_active_plan(db, current_user.tenant_id)
    if not has_stock_management_feature(plan.features if plan else None):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Stock management isn't available on your current plan. Upgrade to Pro to use it.",
        )
    tenant = await _get_tenant(db, current_user)
    tenant.stock_management_enabled = payload.enabled
    await db.commit()
    return StockManagementSettingsResponse(enabled=tenant.stock_management_enabled)


@router.patch(
    "/category-display",
    response_model=CategoryDisplaySettingsResponse,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def update_category_display_setting(
    payload: CategoryDisplaySettingsRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CategoryDisplaySettingsResponse:
    """Tenant-wide toggle for Tamil labels on the POS category rail/strip only — every
    tier, no plan gating (unlike Stock above). Item buttons themselves keep showing
    English+Tamil together regardless (CLAUDE.md §9); this only narrows the category
    nav, and hotel_master.show_tamil_names (printed KOT/bill) is untouched by it.
    """
    tenant = await _get_tenant(db, current_user)
    tenant.show_tamil_categories = payload.show_tamil_categories
    await db.commit()
    return CategoryDisplaySettingsResponse(show_tamil_categories=tenant.show_tamil_categories)


@router.patch(
    "/default-payment-method",
    response_model=DefaultPaymentMethodResponse,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def update_default_payment_method(
    payload: DefaultPaymentMethodRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DefaultPaymentMethodResponse:
    """Tenant-wide — every tier, no plan gating. Pre-selects the payment method on the
    POS billing screen (BillingModal); cashiers can still change it per bill.
    """
    tenant = await _get_tenant(db, current_user)
    tenant.default_payment_method = payload.default_payment_method
    await db.commit()
    return DefaultPaymentMethodResponse(default_payment_method=tenant.default_payment_method)


@router.patch(
    "/report-printing",
    response_model=ReportPrintingSettingsResponse,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def update_report_printing_setting(
    payload: ReportPrintingSettingsRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportPrintingSettingsResponse:
    """Pro Max only — same tenant-level kill-switch shape as stock-management above."""
    plan = await get_active_plan(db, current_user.tenant_id)
    if not has_report_printing_feature(plan.features if plan else None):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Report printing isn't available on your current plan. Upgrade to Pro Max to use it.",
        )
    tenant = await _get_tenant(db, current_user)
    tenant.report_printing_enabled = payload.enabled
    await db.commit()
    return ReportPrintingSettingsResponse(enabled=tenant.report_printing_enabled)


@router.patch(
    "/report-tamil-names",
    response_model=ReportTamilNamesSettingsResponse,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def update_report_tamil_names_setting(
    payload: ReportTamilNamesSettingsRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ReportTamilNamesSettingsResponse:
    """Whether Item Wise/Category Wise report prints show the Tamil name instead of
    English — inert unless report printing itself is on, so gated on the same Pro
    Max-only plan feature as /report-printing above.
    """
    plan = await get_active_plan(db, current_user.tenant_id)
    if not has_report_printing_feature(plan.features if plan else None):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Report printing isn't available on your current plan. Upgrade to Pro Max to use it.",
        )
    tenant = await _get_tenant(db, current_user)
    tenant.report_tamil_names_enabled = payload.enabled
    await db.commit()
    return ReportTamilNamesSettingsResponse(enabled=tenant.report_tamil_names_enabled)


@router.patch(
    "/pos-layout",
    response_model=PosLayoutSettingsResponse,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def update_pos_layout_setting(
    payload: PosLayoutSettingsRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PosLayoutSettingsResponse:
    """Tenant-wide — every tier, no plan gating (a workflow choice, not a premium
    feature). Selects which POS screen a tenant's staff land on at /pos.
    """
    tenant = await _get_tenant(db, current_user)
    tenant.pos_layout = payload.pos_layout
    await db.commit()
    return PosLayoutSettingsResponse(pos_layout=tenant.pos_layout)


@router.patch(
    "/waiter-mandatory",
    response_model=WaiterMandatorySettingsResponse,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def update_waiter_mandatory_setting(
    payload: WaiterMandatorySettingsRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WaiterMandatorySettingsResponse:
    """Common to both POS layouts — gates whether a waiter must be chosen before
    billing a dine-in order. Never applies to non-seating orders (Takeaway/Online
    Delivery), which never require a waiter on either layout regardless of this.
    """
    tenant = await _get_tenant(db, current_user)
    tenant.waiter_mandatory_enabled = payload.enabled
    await db.commit()
    return WaiterMandatorySettingsResponse(enabled=tenant.waiter_mandatory_enabled)


@router.post(
    "/hotel-master/{location_id}/logo",
    response_model=HotelMasterResponse,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def upload_tenant_hotel_master_logo(
    location_id: uuid.UUID,
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HotelMasterResponse:
    tenant = await _get_tenant(db, current_user)
    result = await upload_hotel_master_logo(db, tenant, location_id, file)
    await db.commit()
    return result


@router.delete(
    "/hotel-master/{location_id}/logo",
    response_model=HotelMasterResponse,
    dependencies=[Depends(require_role("tenant_admin"))],
)
async def delete_tenant_hotel_master_logo(
    location_id: uuid.UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HotelMasterResponse:
    result = await remove_hotel_master_logo(db, current_user.tenant_id, location_id)
    await db.commit()
    return result
