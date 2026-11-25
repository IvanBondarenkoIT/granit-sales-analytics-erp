"""Small display helpers for mobile-first templates."""

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
