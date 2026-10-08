"""WooCommerce REST catalog fetch (optional; skips when not configured)."""
from __future__ import annotations

import html
import os
import re
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from django.conf import settings


def woo_configured() -> bool:
    url = (getattr(settings, "WOO_API_URL", None) or os.getenv("WOO_API_URL") or "").strip()
    key = (getattr(settings, "WOO_API_KEY", None) or os.getenv("WOO_API_KEY") or "").strip()
    secret = (getattr(settings, "WOO_API_SECRET", None) or os.getenv("WOO_API_SECRET") or "").strip()
    return bool(url and key and secret)


_QTRANSLATE_PART = re.compile(r"\[:([a-z]{2})\](.*?)(?=\[:[a-z]{0,2}\]|$)", re.S)


def clean_product_name(raw: str, lang: str = "en") -> str:
    """Pick one language from qTranslate markup like '[:ge]...[:en]...[:]'."""
    raw = html.unescape(raw or "")
    parts = {code: text.strip() for code, text in _QTRANSLATE_PART.findall(raw)}
    if not parts:
        return raw.strip()
    return parts.get(lang) or next((t for t in parts.values() if t), "")


def _as_decimal(raw) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None


def _fetch_pages(path: str, extra_params: dict, page_size: int, max_pages: int) -> list[dict]:
    base = (getattr(settings, "WOO_API_URL", None) or os.getenv("WOO_API_URL") or "").rstrip("/")
    key = (getattr(settings, "WOO_API_KEY", None) or os.getenv("WOO_API_KEY") or "").strip()
    secret = (getattr(settings, "WOO_API_SECRET", None) or os.getenv("WOO_API_SECRET") or "").strip()
    timeout = int(getattr(settings, "WOO_API_TIMEOUT", None) or os.getenv("WOO_API_TIMEOUT") or 60)
    if not (base and key and secret):
        raise ValueError("WOO_API_URL / WOO_API_KEY / WOO_API_SECRET are required")

    endpoint = f"{base}/wp-json/wc/v3/{path}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    out: list[dict] = []
    page = 1
    while page <= max_pages:
        resp = requests.get(
            endpoint,
            params={
                "per_page": page_size,
                "page": page,
                "consumer_key": key,
                "consumer_secret": secret,
                **extra_params,
            },
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        out.extend(batch)
        if len(batch) < page_size:
            break
        page += 1
    return out


def parse_woo_product(product: dict) -> dict[str, Any] | None:
    pid = product.get("id")
    if pid is None:
        return None
    return {
        "wp_product_id": str(pid),
        "name": (clean_product_name(product.get("name") or "") or f"#{pid}")[:500],
        "sku": (product.get("sku") or "")[:120],
        "url": (product.get("permalink") or "")[:500],
        "regular_price": _as_decimal(product.get("regular_price")),
        "sale_price": _as_decimal(product.get("sale_price") or None),
        "in_stock": (product.get("stock_status") or "instock") == "instock",
        "category_ids": [
            str(c["id"]) for c in (product.get("categories") or []) if c.get("id") is not None
        ],
    }


def parse_woo_category(category: dict) -> dict[str, Any] | None:
    cid = category.get("id")
    if cid is None:
        return None
    parent = category.get("parent") or 0
    name = clean_product_name(category.get("name") or "") or (category.get("slug") or "").replace("-", " ")
    return {
        "wp_category_id": str(cid),
        "name": (name or f"#{cid}")[:300],
        "slug": (category.get("slug") or "")[:300],
        "parent_id": str(parent) if parent else None,
        "count": int(category.get("count") or 0),
    }


def _lang_params() -> dict:
    lang = (getattr(settings, "WOO_API_LANG", None) or os.getenv("WOO_API_LANG") or "en").strip()
    return {"lang": lang} if lang else {}


def fetch_woo_products(page_size: int = 100, max_pages: int = 200) -> list[dict[str, Any]]:
    raw = _fetch_pages("products", {"status": "publish", **_lang_params()}, page_size, max_pages)
    return [p for p in (parse_woo_product(r) for r in raw) if p]


def fetch_woo_categories(page_size: int = 100, max_pages: int = 50) -> list[dict[str, Any]]:
    raw = _fetch_pages("products/categories", _lang_params(), page_size, max_pages)
    return [c for c in (parse_woo_category(r) for r in raw) if c]
