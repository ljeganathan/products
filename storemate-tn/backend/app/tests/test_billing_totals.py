import uuid

from app.models.enums import DiscountType
from app.services.billing_service import LineInput, compute_bill_totals


def _line(
    unit_price_paise: int,
    qty: float,
    cgst_pct: float,
    sgst_pct: float,
    *,
    igst_pct: float = 0,
    discount_type: DiscountType | None = None,
    discount_value: int | None = None,
) -> LineInput:
    return LineInput(
        item_id=uuid.uuid4(),
        name="Test Item",
        unit_price_paise=unit_price_paise,
        qty=qty,
        cgst_pct=cgst_pct,
        sgst_pct=sgst_pct,
        igst_pct=igst_pct,
        discount_type=discount_type,
        discount_value=discount_value,
    )


def test_single_item_no_discount_exact_round_off() -> None:
    totals = compute_bill_totals([_line(10_000, 2, 9, 9)], None, None)
    assert totals.subtotal_paise == 20_000
    assert totals.discount_paise == 0
    assert totals.cgst_paise == 1_800
    assert totals.sgst_paise == 1_800
    assert totals.round_off_paise == 0
    assert totals.total_paise == 23_600
    assert totals.lines[0].line_total_paise == 23_600


def test_mixed_tax_slabs_in_one_bill() -> None:
    lines = [
        _line(10_000, 1, 2.5, 2.5),  # 5% slab
        _line(20_000, 1, 9, 9),  # 18% slab
    ]
    totals = compute_bill_totals(lines, None, None)
    assert totals.subtotal_paise == 30_000
    assert totals.cgst_paise == 250 + 1_800
    assert totals.sgst_paise == 250 + 1_800
    assert totals.total_paise == 34_100
    assert totals.round_off_paise == 0


def test_bill_level_percent_discount_prorated_across_mixed_slabs() -> None:
    lines = [
        _line(10_000, 1, 2.5, 2.5),  # 5% slab
        _line(20_000, 1, 9, 9),  # 18% slab
    ]
    totals = compute_bill_totals(lines, DiscountType.PERCENT, 1_000)  # 10%

    assert totals.discount_paise == 3_000
    # Line A: taxable 10000-1000=9000 @5% -> 450 tax -> 9450
    # Line B: taxable 20000-2000=18000 @18% -> 3240 tax -> 21240
    assert totals.lines[0].line_total_paise == 9_450
    assert totals.lines[1].line_total_paise == 21_240
    assert sum(line.line_total_paise for line in totals.lines) == 30_690
    # raw_total = 30690 -> nearest rupee = 30700, round_off = +10
    assert totals.round_off_paise == 10
    assert totals.total_paise == 30_700


def test_item_level_flat_discount() -> None:
    totals = compute_bill_totals(
        [_line(5_000, 3, 6, 6, discount_type=DiscountType.FLAT, discount_value=1_000)],
        None,
        None,
    )
    # gross=15000, discount=1000, taxable=14000, cgst=840, sgst=840 -> 15680
    assert totals.discount_paise == 1_000
    assert totals.lines[0].line_total_paise == 15_680
    assert totals.round_off_paise == 20
    assert totals.total_paise == 15_700


def test_fractional_quantity_for_weighed_items() -> None:
    totals = compute_bill_totals([_line(8_000, 0.5, 2.5, 2.5)], None, None)
    assert totals.subtotal_paise == 4_000
    assert totals.total_paise == 4_200
    assert totals.round_off_paise == 0


def test_round_half_even_edge_case() -> None:
    """Python's builtin round() (banker's rounding) is the chosen rule —
    exactly 2.50 rupees rounds to the nearest *even* rupee (2), not always
    up. This test documents that choice explicitly."""
    totals = compute_bill_totals([_line(250, 1, 0, 0)], None, None)
    assert totals.total_paise == 200
    assert totals.round_off_paise == -50


def test_discount_cannot_exceed_line_total() -> None:
    totals = compute_bill_totals(
        [_line(1_000, 1, 0, 0, discount_type=DiscountType.FLAT, discount_value=5_000)],
        None,
        None,
    )
    assert totals.lines[0].discount_paise == 1_000
    assert totals.lines[0].line_total_paise == 0


def test_igst_pct_is_snapshotted_but_not_applied() -> None:
    """A profile's igst_pct (the equivalent inter-state rate, stored on the
    same profile as cgst/sgst per docs/DATABASE_SCHEMA.md) is recorded for
    the record but never added into the tax actually charged — Phase 5
    billing is intra-state only, so only cgst_pct + sgst_pct apply."""
    totals = compute_bill_totals([_line(10_000, 1, 9, 9, igst_pct=18)], None, None)
    assert totals.cgst_paise == 900
    assert totals.sgst_paise == 900
    assert totals.lines[0].tax_profile_snapshot["igst_pct"] == 18


def test_bill_discount_ignored_when_cart_value_is_zero_discount_target() -> None:
    totals = compute_bill_totals(
        [_line(0, 1, 9, 9)], DiscountType.PERCENT, 1_000
    )
    assert totals.discount_paise == 0
    assert totals.total_paise == 0
