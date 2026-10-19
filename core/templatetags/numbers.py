from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template
from django.utils.formats import number_format

register = template.Library()

QTY_STEP = Decimal("0.001")
MONEY_STEP = Decimal("0.01")


def format_money(value) -> str:
    """Amount rounded to 2 decimals for templates and Python callers (charts)."""
    if value is None or value == "":
        return ""
    try:
        number = Decimal(str(value)).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return str(value)
    return number_format(number, decimal_pos=2, use_l10n=True)


@register.filter
def qty(value):
    """Quantity with up to 3 decimals, no trailing zeros, locale separators (kg: 0.25 = 250 g)."""
    if value is None or value == "":
        return ""
    try:
        number = Decimal(str(value)).quantize(QTY_STEP)
    except (InvalidOperation, ValueError):
        return value
    decimals = max(0, -number.normalize().as_tuple().exponent)
    return number_format(number, decimal_pos=decimals, use_l10n=True, force_grouping=True)


@register.filter
def money(value):
    """Amount rounded to 2 decimals (amounts are stored unrounded, like Granit lines)."""
    return format_money(value)
