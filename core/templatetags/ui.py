"""Small display helpers for mobile-first templates."""

from decimal import Decimal

from django import template

register = template.Library()


@register.simple_tag
def count_active(*values):
    """Count values that are set (not None / empty string / False)."""
    return sum(1 for v in values if v not in (None, "", False))


@register.simple_tag
def pct(part, whole, digits=1):
    """Share of part/whole as a percentage string (e.g. 12.5)."""
    try:
        total = float(whole)
        if total == 0:
            return "0"
        value = 100.0 * float(part) / total
    except (TypeError, ValueError):
        return "0"
    if digits == 0:
        return str(int(round(value)))
    return f"{round(value, digits):.{digits}f}".rstrip("0").rstrip(".")


@register.simple_tag
def promo_lift_pre(promo):
    """vs pre-period baseline % for a promo (from prefetched analyses), or None."""
    days = list(promo.analyses.all())
    if not days:
        return None
    actual = sum((row.actual_sales for row in days), Decimal("0"))
    pre = days[0].baseline_pre_period
    if pre is None:
        return None
    baseline = pre * len(days)
    if baseline == 0:
        return None
    return ((actual / baseline) - 1) * Decimal("100")
