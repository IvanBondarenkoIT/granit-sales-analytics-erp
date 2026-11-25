"""Small display helpers for mobile-first templates."""

from django import template

register = template.Library()


@register.simple_tag
def count_active(*values):
    """Count values that are set (not None / empty string / False)."""
    return sum(1 for v in values if v not in (None, "", False))
