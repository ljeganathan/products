STANDARD_TN_FMCG_SLABS = {0.0, 5.0, 12.0, 18.0, 28.0}


def check_tax_slab_warning(cgst_pct: float, sgst_pct: float, igst_pct: float) -> str | None:
    """Return a human-readable warning if the rate doesn't match a standard TN
    FMCG GST slab. Never rejects — exempt/custom rates are legitimate for some
    unregistered or special-case stores (CLAUDE.md §8)."""
    if igst_pct > 0:
        effective = round(igst_pct, 2)
        label = f"IGST {igst_pct}%"
    else:
        effective = round(cgst_pct + sgst_pct, 2)
        label = f"CGST {cgst_pct}% + SGST {sgst_pct}% (total {effective}%)"

    if effective not in STANDARD_TN_FMCG_SLABS:
        slabs = ", ".join(f"{s:g}%" for s in sorted(STANDARD_TN_FMCG_SLABS))
        return (
            f"{label} does not match a standard TN FMCG GST slab ({slabs}). "
            "Allowed, but double-check the rate."
        )
    return None
