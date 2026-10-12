"""Reconcile our «All warehouses» sales with Granit sales documents (DGVDT TYP=0 by REALDATE).

Granit side per store: header sum (= report «Реализация товара по складам», «Сумма с НДС»),
split into goods lines (GDDDT), service lines (GDDDTDDU) and a leftover that nothing explains.
A non-zero leftover means Granit has a kind of line we do not load yet.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db.models import Sum

from core.models import Store
from etl.models import ReconcileSnapshot
from etl.pipeline import (
    _as_date,
    _as_int,
    service_product_id,
    upsert_service_products,
    warehouse_store_routes,
)
from etl.proxy import query_rows
from etl.queries import (
    sql_reconcile_documents,
    sql_reconcile_goods,
    sql_reconcile_headers,
    sql_reconcile_other_types,
    sql_reconcile_services,
    sql_service_catalog,
    sql_warehouses,
)
from sales.models import (
    INVOICE_SOURCES,
    SCOPE_ALL,
    SOURCE_REALIZED,
    SOURCE_SERVICE,
    SaleFact,
)

LEFTOVER_EPS = 0.01
COMPONENTS = (
    "granit_total",
    "granit_goods",
    "granit_services",
    "leftover",
    "ours_goods",
    "ours_services",
    "ours_total",
    "diff",
    "diff_goods",
    "diff_services",
    "pending",
)


def tolerance() -> float:
    return float(getattr(settings, "RECONCILE_TOLERANCE", 1.0))


def month_start(day: date) -> date:
    return day.replace(day=1)


def month_bounds(month: date) -> tuple[date, date]:
    start = month_start(month)
    end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    return start, end


def shift_month(month: date, delta: int) -> date:
    index = month.year * 12 + month.month - 1 + delta
    return date(index // 12, index % 12 + 1, 1)


def _num(value: Any) -> float:
    return round(float(value or 0), 2)


def _ours_by_store(start: date, end: date) -> dict[int, dict[str, float]]:
    rows = (
        SaleFact.objects.for_scope(SCOPE_ALL)
        .filter(sale_date__gte=start, sale_date__lt=end)
        .values("store__granit_id", "source")
        .annotate(amount=Sum("amount"))
    )
    out: dict[int, dict[str, float]] = defaultdict(lambda: {"goods": 0.0, "services": 0.0})
    for row in rows:
        key = "services" if row["source"] == SOURCE_SERVICE else "goods"
        out[row["store__granit_id"]][key] += float(row["amount"] or 0)
    return out


def _pending_by_store(start: date, end: date) -> dict[int, float]:
    """Receipts of the month that Granit has not realized yet (no warehouse document at all)."""
    realized = SaleFact.objects.filter(source=SOURCE_REALIZED).values("granit_sale_id")
    rows = (
        SaleFact.objects.retail()
        .filter(sale_date__gte=start, sale_date__lt=end)
        .exclude(granit_sale_id__in=realized)
        .values("store__granit_id")
        .annotate(amount=Sum("amount"))
    )
    return {row["store__granit_id"]: float(row["amount"] or 0) for row in rows}


def month_state(month: date, today: date | None = None) -> str:
    """closed / open (not finished yet) / partial (before the start of our history)."""
    start, end = month_bounds(month)
    if end > (today or date.today()):
        return "open"
    first = SaleFact.objects.order_by("sale_date").values_list("sale_date", flat=True).first()
    if first is None or first > start:
        return "partial"
    return "closed"


def _ours_by_service(start: date, end: date) -> dict[int, float]:
    rows = (
        SaleFact.objects.filter(sale_date__gte=start, sale_date__lt=end, source=SOURCE_SERVICE)
        .values("product__granit_id")
        .annotate(amount=Sum("amount"))
    )
    return {-row["product__granit_id"]: float(row["amount"] or 0) for row in rows}


def build_month(month: date, routes: dict[int, int] | None = None) -> dict[str, Any]:
    start, end = month_bounds(month)
    period = [start, end]
    if routes is None:
        routes = warehouse_store_routes()
    warehouse_names = {_as_int(r.get("ID")): (r.get("NAME") or "").strip() for r in query_rows(sql_warehouses())}
    services_catalog = upsert_service_products(query_rows(sql_service_catalog()))

    headers = query_rows(sql_reconcile_headers(), period)
    goods = {_as_int(r["WAREHOUSE_ID"]): float(r.get("AMOUNT") or 0) for r in query_rows(sql_reconcile_goods(), period)}
    service_rows = query_rows(sql_reconcile_services(), period)
    other_types = query_rows(sql_reconcile_other_types(), period)

    services_by_wh: dict[int, float] = defaultdict(float)
    granit_by_service: dict[int, float] = defaultdict(float)
    for row in service_rows:
        amount = float(row.get("AMOUNT") or 0)
        services_by_wh[_as_int(row["WAREHOUSE_ID"])] += amount
        granit_by_service[_as_int(row["SERVICE_ID"])] += amount

    stores: dict[int, dict[str, Any]] = {}

    def store_row(store_gid: int) -> dict[str, Any]:
        if store_gid not in stores:
            stores[store_gid] = {"store": store_gid, "warehouses": [], "docs": 0, **{k: 0.0 for k in COMPONENTS}}
        return stores[store_gid]

    for row in headers:
        wh = _as_int(row["WAREHOUSE_ID"])
        store_gid = routes.get(wh, wh)
        target = store_row(store_gid)
        total = float(row.get("AMOUNT") or 0)
        target["granit_total"] += total
        target["granit_goods"] += goods.get(wh, 0.0)
        target["granit_services"] += services_by_wh.get(wh, 0.0)
        target["docs"] += int(row.get("DOCS") or 0)
        target["warehouses"].append(
            {"id": wh, "name": warehouse_names.get(wh) or f"#{wh}", "amount": _num(total)}
        )

    for store_gid, ours in _ours_by_store(start, end).items():
        target = store_row(store_gid)
        target["ours_goods"] += ours["goods"]
        target["ours_services"] += ours["services"]
    for store_gid, amount in _pending_by_store(start, end).items():
        store_row(store_gid)["pending"] += amount

    names = dict(Store.objects.filter(granit_id__in=stores).values_list("granit_id", "name"))
    tol = tolerance()
    flags: list[dict[str, Any]] = []
    totals = {k: 0.0 for k in COMPONENTS}
    totals["docs"] = 0
    for row in stores.values():
        row["name"] = names.get(row["store"]) or f"#{row['store']}"
        row["leftover"] = row["granit_total"] - row["granit_goods"] - row["granit_services"]
        row["ours_total"] = row["ours_goods"] + row["ours_services"]
        row["diff"] = row["ours_total"] - row["granit_total"]
        row["diff_goods"] = row["ours_goods"] - row["granit_goods"]
        row["diff_services"] = row["ours_services"] - row["granit_services"]
        for key in COMPONENTS:
            row[key] = _num(row[key])
            totals[key] += row[key]
        totals["docs"] += row["docs"]
        row["warehouses"].sort(key=lambda w: w["name"])
        row["flags"] = []
        if abs(row["leftover"]) > LEFTOVER_EPS:
            row["flags"].append("leftover")
            flags.append({"kind": "leftover", "store": row["name"], "amount": row["leftover"]})
        if abs(row["diff"]) > tol:
            row["flags"].append("diff")
            flags.append({"kind": "diff", "store": row["name"], "amount": row["diff"]})
    totals = {k: _num(v) if k != "docs" else v for k, v in totals.items()}

    ours_by_service = _ours_by_service(start, end)
    history_exists = SaleFact.objects.filter(sale_date__lt=start).exists()
    services = []
    for service_id in sorted(set(granit_by_service) | set(ours_by_service)):
        product = services_catalog.get(service_id)
        seen_before = SaleFact.objects.filter(
            product__granit_id=service_product_id(service_id), sale_date__lt=start
        ).exists()
        is_new = history_exists and not seen_before
        name = product.name.removeprefix("Услуга: ") if product else f"#{service_id}"
        services.append(
            {
                "id": service_id,
                "name": name,
                "granit": _num(granit_by_service.get(service_id)),
                "ours": _num(ours_by_service.get(service_id)),
                "new": is_new,
            }
        )
        if is_new:
            flags.append({"kind": "new_service", "store": name, "amount": _num(granit_by_service.get(service_id))})

    return {
        "month": start.isoformat(),
        "state": month_state(start),
        "stores": sorted(stores.values(), key=lambda r: r["name"]),
        "totals": totals,
        "services": services,
        "other_types": [
            {"typ": _as_int(r["TYP"]), "docs": int(r.get("DOCS") or 0), "amount": _num(r.get("AMOUNT"))}
            for r in sorted(other_types, key=lambda r: _as_int(r["TYP"]) or 0)
        ],
        "flags": flags,
        "tolerance": tol,
    }


def refresh_month(month: date, routes: dict[int, int] | None = None) -> ReconcileSnapshot:
    data = build_month(month, routes)
    snapshot, _ = ReconcileSnapshot.objects.update_or_create(
        month=month_start(month),
        defaults={
            "data": data,
            "granit_total": Decimal(str(data["totals"]["granit_total"])),
            "ours_total": Decimal(str(data["totals"]["ours_total"])),
            "flag_count": len(data["flags"]) if data["state"] == "closed" else 0,
        },
    )
    return snapshot


def refresh_months(last: date, count: int) -> list[ReconcileSnapshot]:
    routes = warehouse_store_routes()
    return [refresh_month(shift_month(month_start(last), -i), routes) for i in range(count)]


def month_documents(month: date, store_gid: int, limit: int = 100) -> dict[str, Any]:
    """Documents of one store where Granit and our sales disagree.

    Receipt-linked documents are compared through the receipt (SZID): one receipt may be split into
    several warehouse documents (e.g. BATUMIMALL and BATUMIMALL (CUPS)).
    """
    start, end = month_bounds(month)
    routes = warehouse_store_routes()
    warehouses = [wh for wh, gid in routes.items() if gid == store_gid] or [store_gid]
    sql, ids = sql_reconcile_documents(warehouses)
    docs = query_rows(sql, [start, end] + ids)

    keys: dict[tuple[str, int], dict[str, Any]] = {}

    def entry(kind: str, key_id: int) -> dict[str, Any]:
        key = (kind, key_id)
        if key not in keys:
            keys[key] = {
                "kind": kind,
                "key": key_id,
                "docs": [],
                "granit": 0.0,
                "goods": 0.0,
                "services": 0.0,
                "ours": 0.0,
                "ours_dates": set(),
            }
        return keys[key]

    for doc in docs:
        szid = _as_int(doc.get("SZID"))
        item = entry("receipt", szid) if szid is not None else entry("invoice", _as_int(doc["SALE_ID"]))
        item["docs"].append(
            {
                "id": _as_int(doc["SALE_ID"]),
                "nbr": doc.get("NBR"),
                "doc_date": _as_date(doc.get("DOC_DATE")),
                "real_date": _as_date(doc.get("REAL_DATE")),
            }
        )
        item["granit"] += float(doc.get("AMOUNT") or 0)
        item["goods"] += float(doc.get("GOODS") or 0)
        item["services"] += float(doc.get("SERVICES") or 0)

    receipt_ids = [k[1] for k in keys if k[0] == "receipt"]
    invoice_ids = [k[1] for k in keys if k[0] == "invoice"]
    store_facts = SaleFact.objects.for_scope(SCOPE_ALL).filter(store__granit_id=store_gid)
    ours_rows = list(
        store_facts.filter(sale_date__gte=start, sale_date__lt=end)
        .values("source", "granit_sale_id", "sale_date")
        .annotate(amount=Sum("amount"))
    )
    ours_rows += list(
        store_facts.exclude(sale_date__gte=start, sale_date__lt=end)
        .filter(source=SOURCE_REALIZED, granit_sale_id__in=receipt_ids)
        .values("source", "granit_sale_id", "sale_date")
        .annotate(amount=Sum("amount"))
    )
    ours_rows += list(
        store_facts.exclude(sale_date__gte=start, sale_date__lt=end)
        .filter(source__in=INVOICE_SOURCES, granit_sale_id__in=invoice_ids)
        .values("source", "granit_sale_id", "sale_date")
        .annotate(amount=Sum("amount"))
    )
    for row in ours_rows:
        kind = "receipt" if row["source"] == SOURCE_REALIZED else "invoice"
        item = entry(kind, row["granit_sale_id"])
        item["ours"] += float(row["amount"] or 0)
        item["ours_dates"].add(row["sale_date"])

    rows = []
    for item in keys.values():
        item["leftover"] = _num(item["granit"] - item["goods"] - item["services"])
        item["diff"] = _num(item["ours"] - item["granit"])
        for key in ("granit", "goods", "services", "ours"):
            item[key] = _num(item[key])
        item["ours_dates"] = sorted(item["ours_dates"])
        if abs(item["diff"]) > LEFTOVER_EPS or abs(item["leftover"]) > LEFTOVER_EPS:
            rows.append(item)
    rows.sort(key=lambda r: -abs(r["diff"]) - abs(r["leftover"]))
    return {"rows": rows[:limit], "total": len(rows), "checked": len(keys)}
