from decimal import Decimal, InvalidOperation

from django import template
from django.utils.formats import number_format

register = template.Library()

QTY_STEP = Decimal("0.001")


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
