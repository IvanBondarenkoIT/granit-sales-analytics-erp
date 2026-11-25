#!/usr/bin/env python3
"""Minimal local Granit proxy for UI screenshots (reconcile docs).

Does not talk to Firebird. Answers the SQL shapes that month_documents() needs
via etl.proxy (GET /api/health, POST /api/query).

Warehouse IDs avoid seed KIND_GROUP granit_ids (33, 41, 55, 133) so
warehouse_store_routes() does not raise ValueError.

Usage (host):
  python scripts/stub_granit_proxy.py --port 8765

Point the app at it only in a local .env / one-off env (do not commit):
  PROXY_API_URL=http://127.0.0.1:8765
  PROXY_API_TOKEN=local-stub

Docker web → host stub:
  PROXY_API_URL=http://host.docker.internal:8765
"""
from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

DEFAULT_TOKEN = "local-stub"

# Map warehouses → receipt-group stores used by seed_ui_demo (no ID collisions).
WAREHOUSE_GROUPS = [
    {"STORID": 178, "GRPID": 33},
    {"STORID": 130, "GRPID": 41},
    {"STORID": 131, "GRPID": 55},
]
WAREHOUSES = [
    {"ID": 178, "NAME": "HORECA WH"},
    {"ID": 130, "NAME": "BATUMIMALL WH"},
    {"ID": 131, "NAME": "VAKE WH"},
]


def _rows_for_sql(sql: str) -> list[dict[str, Any]]:
    text = sql or ""
    if "FROM STORGRPREF" in text:
        return list(WAREHOUSE_GROUPS)
    if "FROM STORLIST" in text:
        return list(WAREHOUSES)
    # Per-document drill-down (sql_reconcile_documents).
    if "AS SZID" in text or re.search(r"\bDGVDT\b", text):
        return [
            {
                "SALE_ID": 10,
                "NBR": "1",
                "DOC_DATE": "2026-08-03",
                "REAL_DATE": "2026-08-03",
                "SZID": None,
                "WAREHOUSE_ID": 178,
                "AMOUNT": 150.0,
                "GOODS": 40.0,
                "SERVICES": 100.0,
            },
            {
                "SALE_ID": 11,
                "NBR": "2",
                "DOC_DATE": "2026-08-05",
                "REAL_DATE": "2026-08-05",
                "SZID": 9001,
                "WAREHOUSE_ID": 178,
                "AMOUNT": 80.0,
                "GOODS": 80.0,
                "SERVICES": 0.0,
            },
        ]
    # Optional extras so accidental refresh/build_month does not 500 the stub.
    if "FROM HBGDDDU" in text:
        return [{"ID": 1, "NAME": "ремонт кофеварки"}]
    if "TYP NOT IN" in text:
        return [{"TYP": 1, "DOCS": 1, "AMOUNT": 50.0}]
    if "JOIN GDDDTDDU" in text:
        return [{"WAREHOUSE_ID": 178, "SERVICE_ID": 1, "AMOUNT": 100.0}]
    if "JOIN GDDDT G" in text:
        return [{"WAREHOUSE_ID": 178, "AMOUNT": 40.0}]
    if "SUM(H.SUMMA)" in text:
        return [{"WAREHOUSE_ID": 178, "DOCS": 2, "AMOUNT": 230.0}]
    return []


class Handler(BaseHTTPRequestHandler):
    server_version = "StubGranitProxy/1.0"
    token = DEFAULT_TOKEN

    def log_message(self, fmt: str, *args) -> None:
        sys_stderr = __import__("sys").stderr
        print(f"[stub-proxy] {self.address_string()} {fmt % args}", file=sys_stderr)

    def _auth_ok(self) -> bool:
        auth = self.headers.get("Authorization", "")
        return auth == f"Bearer {self.token}"

    def _send(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/api/health":
            if not self._auth_ok():
                self._send(401, {"success": False, "error": "unauthorized"})
                return
            self._send(200, {"success": True, "status": "ok", "stub": True})
            return
        self._send(404, {"success": False, "error": f"unknown path {path}"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path != "/api/query":
            self._send(404, {"success": False, "error": f"unknown path {path}"})
            return
        if not self._auth_ok():
            self._send(401, {"success": False, "error": "unauthorized"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, {"success": False, "error": "invalid JSON"})
            return
        sql = body.get("query") or body.get("sql") or ""
        rows = _rows_for_sql(sql)
        self._send(200, {"success": True, "data": rows})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--token", default=DEFAULT_TOKEN)
    args = parser.parse_args()
    Handler.token = args.token
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(
        f"stub Granit proxy on http://{args.host}:{args.port} "
        f"(token={args.token!r})"
    )
    print("Set PROXY_API_URL / PROXY_API_TOKEN locally; do not commit .env.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
