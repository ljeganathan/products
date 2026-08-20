import uuid
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Bill, BillItem, Category, Item, Payment, Role, User, Waiter
from app.schemas.reports import (
    CashierIncentiveResponse,
    CashierIncentiveRow,
    CashierSalesResponse,
    CashierSalesRow,
    CategoryWiseSalesResponse,
    CategoryWiseSalesRow,
    ItemWiseSalesResponse,
    ItemWiseSalesRow,
    PaymentMethodTotal,
    PosOperatorIncentiveResponse,
    PosOperatorIncentiveRow,
    PosOperatorSalesResponse,
    PosOperatorSalesRow,
    ReportQueryParams,
    SalesSummaryResponse,
    TaxSummaryResponse,
    WaiterIncentiveResponse,
    WaiterIncentiveRow,
    WaiterSalesResponse,
    WaiterSalesRow,
    ZReportResponse,
)


def _bill_filters(tenant_id: uuid.UUID, params: ReportQueryParams) -> list:
    """Every report is built on this same base filter — a single finalized-bill,
    date-range, tenant, (optional) location scope — so no report can silently diverge
    from what `GET /api/v1/bills` itself would return for the same window (CLAUDE.md
    Phase 11 acceptance criteria: reconciles exactly against Phase 09 bill data).
    """
    filters = [
        Bill.tenant_id == tenant_id,
        Bill.status == "finalized",
        Bill.created_at >= params.date_from,
        Bill.created_at < params.date_to + timedelta(days=1),
    ]
    if params.location_id is not None:
        filters.append(Bill.location_id == params.location_id)
    return filters


async def _totals_and_payments(
    session: AsyncSession, tenant_id: uuid.UUID, params: ReportQueryParams
) -> tuple[int, float, float, float, float, float, float, list[PaymentMethodTotal]]:
    """Shared by sales_summary and z_report — both need the exact same bill totals plus
    a per-payment-method breakdown (production feedback round 3 added the breakdown to
    Sales Summary too, to match Z-Report, so this is now the one place that query lives).
    """
    totals = (
        await session.execute(
            select(
                func.count(Bill.id),
                func.coalesce(func.sum(Bill.subtotal), 0),
                func.coalesce(func.sum(Bill.discount_amount), 0),
                func.coalesce(func.sum(Bill.cgst_amount), 0),
                func.coalesce(func.sum(Bill.sgst_amount), 0),
                func.coalesce(func.sum(Bill.round_off_amount), 0),
                func.coalesce(func.sum(Bill.grand_total), 0),
            ).where(*_bill_filters(tenant_id, params))
        )
    ).one()
    bill_count, subtotal, discount, cgst, sgst, round_off, grand_total = totals

    payment_rows = (
        await session.execute(
            select(Payment.method, func.sum(Payment.amount))
            .join(Bill, Bill.id == Payment.bill_id)
            .where(*_bill_filters(tenant_id, params))
            .group_by(Payment.method)
        )
    ).all()
    payments = [PaymentMethodTotal(method=method, amount=float(amount)) for method, amount in payment_rows]

    return (
        bill_count,
        float(subtotal),
        float(discount),
        float(cgst),
        float(sgst),
        float(round_off),
        float(grand_total),
        payments,
    )


async def sales_summary(
    session: AsyncSession, tenant_id: uuid.UUID, params: ReportQueryParams
) -> SalesSummaryResponse:
    bill_count, subtotal, discount, cgst, sgst, round_off, grand_total, payments = await _totals_and_payments(
        session, tenant_id, params
    )
    average_bill_value = round(grand_total / bill_count, 2) if bill_count else 0.0
    return SalesSummaryResponse(
        bill_count=bill_count,
        subtotal=subtotal,
        discount_amount=discount,
        cgst_amount=cgst,
        sgst_amount=sgst,
        round_off_amount=round_off,
        grand_total=grand_total,
        average_bill_value=average_bill_value,
        payments=payments,
    )


async def item_wise_sales(
    session: AsyncSession, tenant_id: uuid.UUID, params: ReportQueryParams
) -> ItemWiseSalesResponse:
    """Item name is snapshotted (`BillItem.name_en_snapshot`) — a renamed/deleted item
    must not retroactively change what a past report shows (Phase 09). Category is a live
    join instead (`Item.category_id` -> `Category`), same "live reference data" treatment
    `category_wise_sales` below already uses, since categories aren't versioned anywhere
    in this schema. `items.category_id` is NOT NULL and items are only ever soft-deleted
    (CLAUDE.md's general pattern), so every `BillItem.item_id` always resolves through to
    a real category — an inner join is safe here, never drops a row.

    Rows are grouped by category and ordered category-major, both levels descending by
    revenue (production feedback round 4: "grouped by the category wise and descending
    order by the sales value... print the category name for each group"). The single
    query below is already ordered by item revenue descending; grouping that sequence by
    category preserves each category's own items in revenue-descending order for free (a
    filtered subsequence of a descending list is still descending) — only the category
    groups themselves need a second, explicit sort by each group's own total.
    """
    rows = (
        await session.execute(
            select(
                BillItem.item_id,
                BillItem.name_en_snapshot,
                BillItem.name_ta_snapshot,
                Item.category_id,
                Category.name_en,
                Category.name_ta,
                func.sum(BillItem.quantity),
                func.sum(BillItem.line_total),
            )
            .join(Bill, Bill.id == BillItem.bill_id)
            .join(Item, Item.id == BillItem.item_id)
            .join(Category, Category.id == Item.category_id)
            .where(*_bill_filters(tenant_id, params))
            .group_by(
                BillItem.item_id,
                BillItem.name_en_snapshot,
                BillItem.name_ta_snapshot,
                Item.category_id,
                Category.name_en,
                Category.name_ta,
            )
            .order_by(func.sum(BillItem.line_total).desc())
        )
    ).all()
    flat_rows = [
        ItemWiseSalesRow(
            item_id=item_id,
            name_en=name_en,
            name_ta=name_ta,
            category_id=cat_id,
            category_name_en=cat_name_en,
            category_name_ta=cat_name_ta,
            quantity_sold=int(qty),
            revenue=float(revenue),
        )
        for item_id, name_en, name_ta, cat_id, cat_name_en, cat_name_ta, qty, revenue in rows
    ]

    cat_totals: dict[uuid.UUID, float] = {}
    items_by_cat: dict[uuid.UUID, list[ItemWiseSalesRow]] = {}
    for r in flat_rows:
        cat_totals[r.category_id] = cat_totals.get(r.category_id, 0.0) + r.revenue
        items_by_cat.setdefault(r.category_id, []).append(r)
    ordered_cat_ids = sorted(cat_totals, key=lambda cid: cat_totals[cid], reverse=True)
    result_rows = [r for cid in ordered_cat_ids for r in items_by_cat[cid]]

    return ItemWiseSalesResponse(
        rows=result_rows, total_revenue=round(sum(r.revenue for r in result_rows), 2)
    )


async def category_wise_sales(
    session: AsyncSession, tenant_id: uuid.UUID, params: ReportQueryParams
) -> CategoryWiseSalesResponse:
    """Unlike item-wise, this joins to the live `categories`/`items` tables rather than
    a snapshot — categories aren't versioned anywhere in this schema (a bill only
    snapshots the item's own name, not its category), so a category rename is treated
    as retroactively relabeling past reports too, consistent with how the rest of the
    app treats category names as live reference data.
    """
    rows = (
        await session.execute(
            select(
                Category.id,
                Category.name_en,
                Category.name_ta,
                func.sum(BillItem.quantity),
                func.sum(BillItem.line_total),
            )
            .join(Bill, Bill.id == BillItem.bill_id)
            .join(Item, Item.id == BillItem.item_id)
            .join(Category, Category.id == Item.category_id)
            .where(*_bill_filters(tenant_id, params))
            .group_by(Category.id, Category.name_en, Category.name_ta)
            .order_by(func.sum(BillItem.line_total).desc())
        )
    ).all()
    result_rows = [
        CategoryWiseSalesRow(
            category_id=cat_id,
            name_en=name_en,
            name_ta=name_ta,
            quantity_sold=int(qty),
            revenue=float(revenue),
        )
        for cat_id, name_en, name_ta, qty, revenue in rows
    ]
    return CategoryWiseSalesResponse(
        rows=result_rows, total_revenue=round(sum(r.revenue for r in result_rows), 2)
    )


async def tax_summary(
    session: AsyncSession, tenant_id: uuid.UUID, params: ReportQueryParams
) -> TaxSummaryResponse:
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(Bill.subtotal - Bill.discount_amount), 0),
                func.coalesce(func.sum(Bill.cgst_amount), 0),
                func.coalesce(func.sum(Bill.sgst_amount), 0),
            ).where(*_bill_filters(tenant_id, params))
        )
    ).one()
    taxable_value, cgst, sgst = row
    return TaxSummaryResponse(
        taxable_value=float(taxable_value),
        cgst_amount=float(cgst),
        sgst_amount=float(sgst),
        total_tax=round(float(cgst) + float(sgst), 2),
    )


async def waiter_wise_sales(
    session: AsyncSession, tenant_id: uuid.UUID, params: ReportQueryParams
) -> WaiterSalesResponse:
    rows = (
        await session.execute(
            select(
                Waiter.id,
                Waiter.name,
                func.count(Bill.id),
                func.sum(Bill.subtotal - Bill.discount_amount),
            )
            .join(Waiter, Waiter.id == Bill.waiter_id)
            .where(*_bill_filters(tenant_id, params), Bill.waiter_id.isnot(None))
            .group_by(Waiter.id, Waiter.name)
            .order_by(func.sum(Bill.subtotal - Bill.discount_amount).desc())
        )
    ).all()
    result_rows = [
        WaiterSalesRow(waiter_id=wid, waiter_name=name, bill_count=count, net_sale_value=float(net))
        for wid, name, count, net in rows
    ]
    return WaiterSalesResponse(
        rows=result_rows, total_net_sale_value=round(sum(r.net_sale_value for r in result_rows), 2)
    )


async def cashier_wise_sales(
    session: AsyncSession, tenant_id: uuid.UUID, params: ReportQueryParams
) -> CashierSalesResponse:
    """Filtered to role=pos_user specifically (not just "whoever's on the bill") since
    `bills.pos_user_id` can point at a tenant_admin or pos_operator who personally rang
    up a sale too — without this filter this report would double-count bills that
    already belong to the tenant_admin's own figures or to `pos_operator_wise_sales`.
    """
    rows = (
        await session.execute(
            select(
                User.id,
                User.user_id,
                User.name,
                func.count(Bill.id),
                func.sum(Bill.subtotal - Bill.discount_amount),
            )
            .join(User, User.id == Bill.pos_user_id)
            .join(Role, Role.id == User.role_id)
            .where(*_bill_filters(tenant_id, params), Role.code == "pos_user")
            .group_by(User.id, User.user_id, User.name)
            .order_by(func.sum(Bill.subtotal - Bill.discount_amount).desc())
        )
    ).all()
    result_rows = [
        CashierSalesRow(
            pos_user_id=uid, login_id=login_id, name=name, bill_count=count, net_sale_value=float(net)
        )
        for uid, login_id, name, count, net in rows
    ]
    return CashierSalesResponse(
        rows=result_rows, total_net_sale_value=round(sum(r.net_sale_value for r in result_rows), 2)
    )


async def waiter_incentive_report(
    session: AsyncSession, tenant_id: uuid.UUID, params: ReportQueryParams
) -> WaiterIncentiveResponse:
    """Payout worksheet — `incentive_amount` is a SUM of the already-computed
    `bills.waiter_incentive_amount` (Phase 09 finalize time), not a fresh
    rate × net-sale-value calculation, so it can never drift from what staff saw live
    on the bill (CLAUDE.md §11 acceptance criteria).
    """
    rows = (
        await session.execute(
            select(
                Waiter.id,
                Waiter.name,
                func.sum(Bill.subtotal - Bill.discount_amount),
                func.sum(Bill.waiter_incentive_amount),
            )
            .join(Waiter, Waiter.id == Bill.waiter_id)
            .where(
                *_bill_filters(tenant_id, params),
                Bill.waiter_id.isnot(None),
                Bill.waiter_incentive_amount.isnot(None),
            )
            .group_by(Waiter.id, Waiter.name)
            # A 0%-rate waiter still gets a non-NULL (but zero) incentive_amount per
            # bill — exclude them from this payout worksheet entirely rather than
            # listing a ₹0.00 row nobody needs to act on.
            .having(func.sum(Bill.waiter_incentive_amount) > 0)
            .order_by(func.sum(Bill.waiter_incentive_amount).desc())
        )
    ).all()
    result_rows = [
        WaiterIncentiveRow(
            waiter_id=wid, waiter_name=name, net_sale_value=float(net), incentive_amount=float(inc)
        )
        for wid, name, net, inc in rows
    ]
    return WaiterIncentiveResponse(
        rows=result_rows, total_incentive_amount=round(sum(r.incentive_amount for r in result_rows), 2)
    )


async def cashier_incentive_report(
    session: AsyncSession, tenant_id: uuid.UUID, params: ReportQueryParams
) -> CashierIncentiveResponse:
    """Filtered to role=pos_user specifically — see cashier_wise_sales' docstring."""
    rows = (
        await session.execute(
            select(
                User.id,
                User.user_id,
                User.name,
                func.sum(Bill.subtotal - Bill.discount_amount),
                func.sum(Bill.cashier_incentive_amount),
            )
            .join(User, User.id == Bill.pos_user_id)
            .join(Role, Role.id == User.role_id)
            .where(
                *_bill_filters(tenant_id, params),
                Bill.cashier_incentive_amount.isnot(None),
                Role.code == "pos_user",
            )
            .group_by(User.id, User.user_id, User.name)
            .having(func.sum(Bill.cashier_incentive_amount) > 0)
            .order_by(func.sum(Bill.cashier_incentive_amount).desc())
        )
    ).all()
    result_rows = [
        CashierIncentiveRow(
            pos_user_id=uid,
            login_id=login_id,
            name=name,
            net_sale_value=float(net),
            incentive_amount=float(inc),
        )
        for uid, login_id, name, net, inc in rows
    ]
    return CashierIncentiveResponse(
        rows=result_rows, total_incentive_amount=round(sum(r.incentive_amount for r in result_rows), 2)
    )


async def pos_operator_wise_sales(
    session: AsyncSession, tenant_id: uuid.UUID, params: ReportQueryParams
) -> PosOperatorSalesResponse:
    """Mirrors cashier_wise_sales exactly, filtered to role=pos_operator instead."""
    rows = (
        await session.execute(
            select(
                User.id,
                User.user_id,
                User.name,
                func.count(Bill.id),
                func.sum(Bill.subtotal - Bill.discount_amount),
            )
            .join(User, User.id == Bill.pos_user_id)
            .join(Role, Role.id == User.role_id)
            .where(*_bill_filters(tenant_id, params), Role.code == "pos_operator")
            .group_by(User.id, User.user_id, User.name)
            .order_by(func.sum(Bill.subtotal - Bill.discount_amount).desc())
        )
    ).all()
    result_rows = [
        PosOperatorSalesRow(
            pos_user_id=uid, login_id=login_id, name=name, bill_count=count, net_sale_value=float(net)
        )
        for uid, login_id, name, count, net in rows
    ]
    return PosOperatorSalesResponse(
        rows=result_rows, total_net_sale_value=round(sum(r.net_sale_value for r in result_rows), 2)
    )


async def pos_operator_incentive_report(
    session: AsyncSession, tenant_id: uuid.UUID, params: ReportQueryParams
) -> PosOperatorIncentiveResponse:
    """Mirrors cashier_incentive_report exactly, filtered to role=pos_operator instead."""
    rows = (
        await session.execute(
            select(
                User.id,
                User.user_id,
                User.name,
                func.sum(Bill.subtotal - Bill.discount_amount),
                func.sum(Bill.cashier_incentive_amount),
            )
            .join(User, User.id == Bill.pos_user_id)
            .join(Role, Role.id == User.role_id)
            .where(
                *_bill_filters(tenant_id, params),
                Bill.cashier_incentive_amount.isnot(None),
                Role.code == "pos_operator",
            )
            .group_by(User.id, User.user_id, User.name)
            .having(func.sum(Bill.cashier_incentive_amount) > 0)
            .order_by(func.sum(Bill.cashier_incentive_amount).desc())
        )
    ).all()
    result_rows = [
        PosOperatorIncentiveRow(
            pos_user_id=uid,
            login_id=login_id,
            name=name,
            net_sale_value=float(net),
            incentive_amount=float(inc),
        )
        for uid, login_id, name, net, inc in rows
    ]
    return PosOperatorIncentiveResponse(
        rows=result_rows, total_incentive_amount=round(sum(r.incentive_amount for r in result_rows), 2)
    )


async def z_report(
    session: AsyncSession, tenant_id: uuid.UUID, params: ReportQueryParams
) -> ZReportResponse:
    """Daily shift-close — `params.date_from`/`date_to` are expected to be the same
    single day, but nothing here forces that; passing a wider range just produces a
    multi-day shift-close total, which is a harmless generalization.
    """
    bill_count, subtotal, discount, cgst, sgst, round_off, grand_total, payments = await _totals_and_payments(
        session, tenant_id, params
    )

    return ZReportResponse(
        report_date=params.date_from,
        bill_count=bill_count,
        subtotal=subtotal,
        discount_amount=discount,
        cgst_amount=cgst,
        sgst_amount=sgst,
        round_off_amount=round_off,
        grand_total=grand_total,
        payments=payments,
    )
