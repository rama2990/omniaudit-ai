from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal(0)


def rp(x) -> Decimal:
    """Round to whole rupiah, half-up."""
    return Decimal(x).quantize(Decimal(1), ROUND_HALF_UP)


def fmt_rp(x) -> str:
    return "Rp" + f"{int(rp(x)):,}".replace(",", ".")
