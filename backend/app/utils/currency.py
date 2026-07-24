def format_paise_inr(paise: int) -> str:
    """Server-side ₹ formatting (Indian digit grouping) for the one place
    the backend legitimately renders money for humans directly — the PDF
    dashboard export and the scheduled digest email. The frontend still
    owns all in-app formatting (CLAUDE.md §3) via `formatPaise` in
    utils/money.ts; this is not a duplicate of that, it's a Python-side
    equivalent for output the browser never touches."""
    rupees = paise / 100
    sign = "-" if rupees < 0 else ""
    whole = int(abs(rupees))
    frac = round((abs(rupees) - whole) * 100)

    digits = str(whole)
    if len(digits) > 3:
        last3 = digits[-3:]
        rest = digits[:-3]
        groups: list[str] = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        digits = ",".join([*groups, last3])

    return f"{sign}₹{digits}.{frac:02d}"


def paise_to_plain_amount(paise: int) -> str:
    """"1234.56" with no currency symbol or thousands separator — for CSV
    export rows that feed into spreadsheets/accounting software, mirrors
    the frontend's `paiseToPlainAmount` (utils/money.ts)."""
    return f"{paise / 100:.2f}"
