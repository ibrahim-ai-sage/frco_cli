"""Formatage des montants pour un éventuel affichage Markdown."""

from decimal import Decimal, ROUND_HALF_UP


def format_revenue_eur(amount: int | float) -> str:
    """Présente un chiffre d'affaires numérique en euros pour la lecture.

    Args:
        amount: Chiffre d'affaires en euros.

    Returns:
        Montant français, abrégé à partir d'un million d'euros.
    """
    value = Decimal(str(amount))
    if value >= 1_000_000_000:
        display, unit = value / Decimal(1_000_000_000), "Md€"
    elif value >= 1_000_000:
        display, unit = value / Decimal(1_000_000), "M€"
    else:
        display, unit = value, "€"

    precision = 0 if unit == "€" and value == value.to_integral_value() else 2
    quantum = Decimal("1") if precision == 0 else Decimal("0.01")
    rounded = display.quantize(quantum, rounding=ROUND_HALF_UP)
    formatted = f"{rounded:,.{precision}f}".replace(",", " ").replace(".", ",")
    return f"{formatted} {unit}"
