"""Google Sheets helpers for Granit ↔ Woo mapping (optional deps)."""
from __future__ import annotations

import base64
import json
import os
import re
from dataclasses import dataclass
from typing import Any

from django.conf import settings


@dataclass(frozen=True)
class GranitWpPair:
    wp_product_id: str
    granit_id: int


def _norm_header(h: str) -> str:
    return re.sub(r"[\s_\-]+", "", (h or "").lower())


def _norm_id(value: Any) -> str:
    s = str(value or "").strip()
    if not s:
        return ""
    if re.fullmatch(r"\d+\.0+", s):
        s = s.split(".", 1)[0]
    return s


def parse_granit_sheet_rows(rows: list[dict[str, str]]) -> list[GranitWpPair]:
    if not rows:
        return []
    sample = rows[0]
    norm_map = {_norm_header(k): k for k in sample.keys()}
    wp_key = None
    for cand in ("wp-id", "wp_id", "wpid", "wp id"):
        key = norm_map.get(_norm_header(cand))
        if key:
            wp_key = key
            break
    granit_key = None
    for cand in ("granit_id", "granitid", "granit id"):
        key = norm_map.get(_norm_header(cand))
        if key:
            granit_key = key
            break
    if not wp_key or not granit_key:
        raise ValueError(
            f"granit sheet must have granit_id and wp-id columns; got: {list(sample.keys())}"
        )
    by_wp: dict[str, int] = {}
    for row in rows:
        wp_id = _norm_id(row.get(wp_key, ""))
        granit_raw = _norm_id(row.get(granit_key, ""))
        if not wp_id or not granit_raw:
            continue
        try:
            granit_id = int(granit_raw)
        except ValueError:
            continue
        by_wp[wp_id] = granit_id
    return [GranitWpPair(wp_product_id=wp, granit_id=gid) for wp, gid in by_wp.items()]


def sheets_configured() -> bool:
    url = (getattr(settings, "GOOGLE_SHEETS_URL", None) or os.getenv("GOOGLE_SHEETS_URL") or "").strip()
    path = (
        getattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON_PATH", None)
        or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH")
        or ""
    ).strip()
    b64 = (
        getattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON_BASE64", None)
        or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_BASE64")
        or ""
    ).strip()
    return bool(url and (path or b64))


def _service_account_info() -> dict[str, Any]:
    b64 = (
        getattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON_BASE64", None)
        or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_BASE64")
        or ""
    ).strip()
    if b64:
        return json.loads(base64.b64decode(b64.encode("utf-8")).decode("utf-8"))
    path = (
        getattr(settings, "GOOGLE_SERVICE_ACCOUNT_JSON_PATH", None)
        or os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH")
        or ""
    ).strip()
    if path:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    raise ValueError("Set GOOGLE_SERVICE_ACCOUNT_JSON_PATH or GOOGLE_SERVICE_ACCOUNT_JSON_BASE64")


def fetch_granit_mapping_rows() -> list[dict[str, str]]:
    """Read mapping tab via gspread. Raises ImportError if google libs missing."""
    import gspread
    from google.oauth2.service_account import Credentials

    url = (getattr(settings, "GOOGLE_SHEETS_URL", None) or os.getenv("GOOGLE_SHEETS_URL") or "").strip()
    tab = (
        getattr(settings, "GOOGLE_SHEETS_TAB_GRANIT", None)
        or os.getenv("GOOGLE_SHEETS_TAB_GRANIT")
        or "granit"
    ).strip() or "granit"
    if not url:
        raise ValueError("GOOGLE_SHEETS_URL is not set")
    creds = Credentials.from_service_account_info(
        _service_account_info(),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    client = gspread.authorize(creds)
    ws = client.open_by_url(url).worksheet(tab)
    values = ws.get_all_values()
    if not values:
        return []
    headers = [str(h).strip() for h in values[0]]
    rows: list[dict[str, str]] = []
    for line in values[1:]:
        if not any(str(c).strip() for c in line):
            continue
        row = {}
        for i, header in enumerate(headers):
            if not header:
                continue
            row[header] = str(line[i] if i < len(line) else "").strip()
        rows.append(row)
    return rows
