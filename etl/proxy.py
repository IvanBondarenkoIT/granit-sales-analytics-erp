"""Read-only client for firebird-db-proxy. Do not log tokens."""
from __future__ import annotations

import logging
import re
from typing import Any

import requests
from django.conf import settings
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

_SELECT_ONLY = re.compile(r"^\s*(WITH|SELECT)\b", re.IGNORECASE | re.DOTALL)


class ProxyApiError(RuntimeError):
    """firebird-db-proxy request failed."""


def _base_url() -> str:
    base = (getattr(settings, "PROXY_API_URL", "") or "").strip().rstrip("/")
    if not base:
        raise ProxyApiError("Set PROXY_API_URL in .env")
    if base.endswith("/api/query"):
        return base[: -len("/api/query")]
    return base


def _token() -> str:
    token = (getattr(settings, "PROXY_API_TOKEN", "") or "").strip()
    if not token:
        raise ProxyApiError("Set PROXY_API_TOKEN in .env")
    return token


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
    }


def _json_params(params: list[Any] | None) -> list[Any]:
    out: list[Any] = []
    for item in params or []:
        if hasattr(item, "isoformat"):
            out.append(item.isoformat())
        else:
            out.append(item)
    return out


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if isinstance(payload, list):
        if not payload:
            return []
        if isinstance(payload[0], dict):
            return payload
        raise ProxyApiError("Proxy returned a list of non-objects")
    if not isinstance(payload, dict):
        raise ProxyApiError(f"Unexpected proxy payload type: {type(payload)!r}")
    if payload.get("success") is False:
        raise ProxyApiError(str(payload.get("error") or payload.get("message") or "query failed"))
    if payload.get("error"):
        raise ProxyApiError(str(payload["error"]))
    data = payload.get("data")
    if isinstance(data, list):
        if not data or isinstance(data[0], dict):
            return data
    if isinstance(data, dict):
        return _rows_from_payload(data)
    rows = payload.get("rows")
    columns = payload.get("columns") or payload.get("fields") or payload.get("colnames")
    if isinstance(rows, list) and rows and isinstance(rows[0], dict):
        return rows
    if columns is not None and isinstance(rows, list):
        return [dict(zip(columns, row)) for row in rows]
    if payload.get("result") is not None:
        return _rows_from_payload(payload["result"])
    if data is None and rows is None:
        return []
    raise ProxyApiError("Could not parse proxy JSON (expected data rows)")


def _normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {}
        for key, value in row.items():
            name = str(key).strip().upper()
            if isinstance(value, str):
                value = value.strip()
            item[name] = value
        normalized.append(item)
    return normalized


def health_check() -> dict[str, Any]:
    url = f"{_base_url()}/api/health"
    timeout = getattr(settings, "PROXY_API_TIMEOUT", 60)
    try:
        resp = _session().get(url, headers=_headers(), timeout=timeout)
    except requests.RequestException as exc:
        raise ProxyApiError(f"Proxy health check failed: {exc}") from exc
    if resp.status_code >= 400:
        raise ProxyApiError(f"Proxy health HTTP {resp.status_code}")
    try:
        return resp.json()
    except ValueError as exc:
        raise ProxyApiError("Proxy health returned non-JSON") from exc


def query_rows(sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
    if not _SELECT_ONLY.match(sql or ""):
        raise ProxyApiError("Only SELECT/WITH queries are allowed")
    url = f"{_base_url()}/api/query"
    timeout = getattr(settings, "PROXY_API_TIMEOUT", 60)
    body: dict[str, Any] = {"query": sql}
    if params:
        body["params"] = _json_params(params)
    logger.debug("proxy query (%s chars)", len(sql))
    try:
        resp = _session().post(url, json=body, headers=_headers(), timeout=timeout)
    except requests.RequestException as exc:
        raise ProxyApiError(f"Proxy query failed: {exc}") from exc
    if resp.status_code >= 400:
        detail = (resp.text or resp.reason)[:300]
        raise ProxyApiError(f"Proxy query HTTP {resp.status_code}: {detail}")
    try:
        payload = resp.json()
    except ValueError as exc:
        raise ProxyApiError("Proxy query returned non-JSON") from exc
    return _normalize_rows(_rows_from_payload(payload))
