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


def _granit_sheet_meta() -> tuple[str, str]:
    url = (getattr(settings, "GOOGLE_SHEETS_URL", None) or os.getenv("GOOGLE_SHEETS_URL") or "").strip()
    tab = (
        getattr(settings, "GOOGLE_SHEETS_TAB_GRANIT", None)
        or os.getenv("GOOGLE_SHEETS_TAB_GRANIT")
        or "granit"
    ).strip() or "granit"
    if not url:
        raise ValueError("GOOGLE_SHEETS_URL is not set")
    return url, tab


def _open_granit_worksheet(*, readonly: bool = True, insecure_ssl: bool = False):
    import gspread
    from google.oauth2.service_account import Credentials

    url, tab = _granit_sheet_meta()
    scope = (
        "https://www.googleapis.com/auth/spreadsheets.readonly"
        if readonly
        else "https://www.googleapis.com/auth/spreadsheets"
    )
    creds = Credentials.from_service_account_info(
        _service_account_info(),
        scopes=[scope],
    )
    if insecure_ssl:
        # Corporate MITM / missing CA chain — only for explicit operator opt-in.
        import google.auth.transport.requests as ga_requests
        import requests
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        _orig_request = requests.Session.request

        def _insecure_request(self, method, url, *args, **kwargs):  # noqa: ANN001
            kwargs["verify"] = False
            return _orig_request(self, method, url, *args, **kwargs)

        requests.Session.request = _insecure_request  # type: ignore[method-assign]
        try:
            session = ga_requests.AuthorizedSession(creds)
            session.verify = False
            client = gspread.Client(auth=creds, session=session)
            return client.open_by_url(url).worksheet(tab)
        finally:
            requests.Session.request = _orig_request  # type: ignore[method-assign]
    client = gspread.authorize(creds)
    return client.open_by_url(url).worksheet(tab)


def _header_column_indexes(headers: list[str]) -> tuple[int, int]:
    """Return 0-based indexes of wp-id and granit_id columns."""
    norm_map = {_norm_header(h): i for i, h in enumerate(headers) if str(h).strip()}
    wp_idx = None
    for cand in ("wp-id", "wp_id", "wpid", "wp id"):
        if _norm_header(cand) in norm_map:
            wp_idx = norm_map[_norm_header(cand)]
            break
    granit_idx = None
    for cand in ("granit_id", "granitid", "granit id"):
        if _norm_header(cand) in norm_map:
            granit_idx = norm_map[_norm_header(cand)]
            break
    if wp_idx is None or granit_idx is None:
        raise ValueError(f"granit sheet must have granit_id and wp-id columns; got: {headers}")
    return wp_idx, granit_idx


def fetch_granit_mapping_rows() -> list[dict[str, str]]:
    """Read mapping tab via gspread. Raises ImportError if google libs missing."""
    ws = _open_granit_worksheet(readonly=True)
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


def set_granit_sheet_wp_id(
    granit_id: int, wp_product_id: str, *, insecure_ssl: bool = False
) -> dict[str, Any]:
    """
    Update (or append) the granit sheet row so granit_id maps to wp_product_id.
    Requires Sheets write access for the service account.
    """
    wp_product_id = _norm_id(wp_product_id)
    if not wp_product_id:
        raise ValueError("wp_product_id is empty")
    ws = _open_granit_worksheet(readonly=False, insecure_ssl=insecure_ssl)
    values = ws.get_all_values()
    if not values:
        raise ValueError("granit sheet is empty")
    headers = [str(h).strip() for h in values[0]]
    wp_idx, granit_idx = _header_column_indexes(headers)
    target = str(int(granit_id))
    updated_rows: list[int] = []
    for row_num, line in enumerate(values[1:], start=2):  # 1-based sheet rows
        cell = line[granit_idx] if granit_idx < len(line) else ""
        if _norm_id(cell) != target:
            continue
        # gspread uses 1-based column index
        ws.update_cell(row_num, wp_idx + 1, wp_product_id)
        updated_rows.append(row_num)
    if updated_rows:
        return {"action": "updated", "rows": updated_rows, "granit_id": granit_id, "wp_product_id": wp_product_id}
    # Append a new mapping row with only the two known columns filled.
    new_line = [""] * len(headers)
    new_line[wp_idx] = wp_product_id
    new_line[granit_idx] = target
    ws.append_row(new_line, value_input_option="USER_ENTERED")
    return {
        "action": "appended",
        "rows": [len(values) + 1],
        "granit_id": granit_id,
        "wp_product_id": wp_product_id,
    }
