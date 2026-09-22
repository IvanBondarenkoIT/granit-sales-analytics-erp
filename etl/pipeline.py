"""Load Granit dims/facts from firebird-db-proxy into Postgres."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import (
    Client,
    Product,
    ProductGroup,
    ProductParameter,
    ProductParameterValue,
    Store,
)
from etl.models import ETLRun, ETLWatermark
from etl.proxy import query_rows
from etl.queries import (
    STOCK_CHUNK,
    sql_clients,
    sql_clients_by_ids,
    sql_product_groups,
    sql_product_parameters,
    sql_products,
    sql_sales_day,
    sql_stock_chunk,
    sql_stores,
)
from sales.models import SaleFact, StockSnapshot


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_str(value: Any, limit: int = 500) -> str:
    if value is None:
        return ""
    return str(value).strip()[:limit]


def _as_decimal(value: Any) -> Decimal:
    if value is None or value == "":
        return Decimal("0")
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _as_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if "T" in text:
        text = text.split("T", 1)[0]
    if " " in text:
        text = text.split(" ", 1)[0]
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def start_run(etl_type: str) -> ETLRun:
    return ETLRun.objects.create(etl_type=etl_type, status="running")


def finish_run(
    run: ETLRun,
    *,
    inserted: int = 0,
    updated: int = 0,
    processed: int = 0,
    error: str = "",
    details: dict | None = None,
) -> ETLRun:
    run.records_inserted = inserted
    run.records_updated = updated
    run.records_processed = processed
    run.log_details = details or {}
    run.completed_at = timezone.now()
    run.status = "failed" if error else "success"
    run.error_message = error[:4000] if error else ""
    run.save()
    return run


def set_watermark(entity: str, last_date: date | None) -> None:
    mark, _ = ETLWatermark.objects.get_or_create(entity_name=entity)
    mark.last_processed_date = last_date
    mark.save(update_fields=["last_processed_date", "updated_at"])


def company_ledger_store() -> Store:
    store, _ = Store.objects.get_or_create(
        granit_id=settings.COMPANY_LEDGER_STORE_ID,
        defaults={"name": "Company ledger"},
    )
    return store


def upsert_stores(rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
    inserted = updated = 0
    for row in rows:
        granit_id = _as_int(row.get("ID"))
        if granit_id is None:
            continue
        _, created = Store.objects.update_or_create(
            granit_id=granit_id,
            defaults={"name": _as_str(row.get("NAME"), 200) or f"#{granit_id}"},
        )
        if created:
            inserted += 1
        else:
            updated += 1
    return inserted, updated


def upsert_groups(rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
    inserted = updated = 0
    for row in rows:
        granit_id = _as_int(row.get("ID"))
        if granit_id is None:
            continue
        _, created = ProductGroup.objects.update_or_create(
            granit_id=granit_id,
            defaults={"name": _as_str(row.get("NAME"), 200) or f"#{granit_id}"},
        )
        if created:
            inserted += 1
        else:
            updated += 1
    return inserted, updated


def upsert_products(rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
    inserted = updated = 0
    groups = {g.granit_id: g for g in ProductGroup.objects.all()}
    for row in rows:
        granit_id = _as_int(row.get("PRODUCT_ID") or row.get("ID"))
        if granit_id is None:
            continue
        group_id = _as_int(row.get("GROUP_ID"))
        group = groups.get(group_id) if group_id is not None else None
        _, created = Product.objects.update_or_create(
            granit_id=granit_id,
            defaults={
                "name": _as_str(row.get("PRODUCT_NAME") or row.get("NAME"), 500) or f"#{granit_id}",
                "group": group,
            },
        )
        if created:
            inserted += 1
        else:
            updated += 1
    return inserted, updated


def upsert_parameters(rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
    inserted = updated = 0
    products = {p.granit_id: p for p in Product.objects.all()}
    for row in rows:
        param_id = _as_int(row.get("PARAM_ID"))
        product_id = _as_int(row.get("PRODUCT_ID"))
        value_id = _as_int(row.get("PARAM_VALUE_ID"))
        if param_id is None or product_id is None:
            continue
        parameter, _ = ProductParameter.objects.update_or_create(
            granit_id=param_id,
            defaults={"name": _as_str(row.get("PARAM_NAME"), 200) or f"#{param_id}"},
        )
        value = None
        if value_id is not None:
            value, created_val = ProductParameterValue.objects.update_or_create(
                granit_id=value_id,
                defaults={
                    "parameter": parameter,
                    "label": _as_str(row.get("PARAM_VALUE_LABEL"), 200) or f"#{value_id}",
                },
            )
            if created_val:
                inserted += 1
            else:
                updated += 1
        product = products.get(product_id)
        if product is None:
            continue
        product.parameter = parameter
        product.parameter_value = value
        product.save(update_fields=["parameter", "parameter_value", "updated_at"])
        updated += 1
    return inserted, updated


def upsert_clients(rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
    inserted = updated = 0
    for row in rows:
        granit_id = _as_int(row.get("CLIENT_ID") or row.get("ID"))
        if granit_id is None:
            continue
        _, created = Client.objects.update_or_create(
            granit_id=granit_id,
            defaults={
                "name": _as_str(row.get("CLIENT_NAME") or row.get("NAME"), 200),
                "phone": _as_str(row.get("PHONE"), 50),
            },
        )
        if created:
            inserted += 1
        else:
            updated += 1
    return inserted, updated


def ensure_store(granit_id: int) -> Store:
    store, _ = Store.objects.get_or_create(
        granit_id=granit_id,
        defaults={"name": f"#{granit_id}"},
    )
    return store


def ensure_product(granit_id: int) -> Product:
    product, _ = Product.objects.get_or_create(
        granit_id=granit_id,
        defaults={"name": f"#{granit_id}", "is_active": True},
    )
    return product


def ensure_client(granit_id: int | None) -> Client | None:
    if granit_id is None:
        return None
    client, _ = Client.objects.get_or_create(
        granit_id=granit_id,
        defaults={"name": f"#{granit_id}"},
    )
    return client


def load_dims() -> dict[str, int]:
    stores_i, stores_u = upsert_stores(query_rows(sql_stores()))
    groups_i, groups_u = upsert_groups(query_rows(sql_product_groups()))
    products_i, products_u = upsert_products(query_rows(sql_products()))
    param_sql, param_params = sql_product_parameters()
    params_i, params_u = upsert_parameters(query_rows(param_sql, param_params))
    clients_i, clients_u = upsert_clients(query_rows(sql_clients()))
    return {
        "stores_inserted": stores_i,
        "stores_updated": stores_u,
        "groups_inserted": groups_i,
        "groups_updated": groups_u,
        "products_inserted": products_i,
        "products_updated": products_u,
        "params_inserted": params_i,
        "params_updated": params_u,
        "clients_inserted": clients_i,
        "clients_updated": clients_u,
    }


def _backfill_missing_clients(client_ids: set[int]) -> None:
    missing = client_ids - set(Client.objects.filter(granit_id__in=client_ids).values_list("granit_id", flat=True))
    if not missing:
        return
    ids = list(missing)
    for i in range(0, len(ids), 200):
        chunk = ids[i : i + 200]
        sql, params = sql_clients_by_ids(chunk)
        upsert_clients(query_rows(sql, params))
        still = set(chunk) - set(
            Client.objects.filter(granit_id__in=chunk).values_list("granit_id", flat=True)
        )
        for cid in still:
            ensure_client(cid)


def load_sales_day(sale_date: date) -> int:
    sql, base_params = sql_sales_day()
    rows = query_rows(sql, base_params + [sale_date, sale_date + timedelta(days=1)])
    if not rows:
        with transaction.atomic():
            deleted, _ = SaleFact.objects.filter(sale_date=sale_date).delete()
        return 0

    store_ids = {_as_int(r.get("STORE_ID")) for r in rows}
    product_ids = {_as_int(r.get("PRODUCT_ID")) for r in rows}
    client_ids = {_as_int(r.get("CLIENT_ID")) for r in rows}
    store_ids.discard(None)
    product_ids.discard(None)
    client_ids.discard(None)

    for sid in store_ids:
        ensure_store(sid)
    for pid in product_ids:
        ensure_product(pid)
    _backfill_missing_clients(client_ids)

    stores = {s.granit_id: s for s in Store.objects.filter(granit_id__in=store_ids)}
    products = {p.granit_id: p for p in Product.objects.filter(granit_id__in=product_ids)}
    clients = {c.granit_id: c for c in Client.objects.filter(granit_id__in=client_ids)}

    facts: list[SaleFact] = []
    seen: set[tuple[int, int]] = set()
    for row in rows:
        sale_id = _as_int(row.get("SALE_ID"))
        line_id = _as_int(row.get("LINE_ID"))
        store_id = _as_int(row.get("STORE_ID"))
        product_id = _as_int(row.get("PRODUCT_ID"))
        if sale_id is None or line_id is None or store_id is None or product_id is None:
            continue
        key = (sale_id, line_id)
        if key in seen:
            continue
        seen.add(key)
        store = stores.get(store_id)
        product = products.get(product_id)
        if store is None or product is None:
            continue
        client_id = _as_int(row.get("CLIENT_ID"))
        facts.append(
            SaleFact(
                sale_date=_as_date(row.get("SALE_DATE")) or sale_date,
                store=store,
                client=clients.get(client_id) if client_id is not None else None,
                product=product,
                quantity=_as_decimal(row.get("QTY")),
                amount=_as_decimal(row.get("AMOUNT")),
                granit_sale_id=sale_id,
                granit_line_id=line_id,
            )
        )

    with transaction.atomic():
        SaleFact.objects.filter(sale_date=sale_date).delete()
        SaleFact.objects.bulk_create(facts, batch_size=1000)
    return len(facts)


def load_sales_range(date_from: date, date_to: date, progress=None) -> dict[str, int]:
    """Load [date_from, date_to) one calendar day at a time."""
    if date_to <= date_from:
        raise ValueError("--to must be after --from")
    total = 0
    days = 0
    current = date_from
    while current < date_to:
        count = load_sales_day(current)
        total += count
        days += 1
        if progress:
            progress(current, count)
        current += timedelta(days=1)
    last = date_to - timedelta(days=1)
    set_watermark("sales", last)
    return {"days": days, "rows": total}


def load_stock(snapshot_date: date | None = None) -> dict[str, int]:
    snapshot_date = snapshot_date or (date.today() - timedelta(days=1))
    store = company_ledger_store()
    product_ids = list(Product.objects.values_list("granit_id", flat=True))
    if not product_ids:
        return {"rows": 0, "active": 0}

    stock_by_id: dict[int, Decimal] = {}
    for i in range(0, len(product_ids), STOCK_CHUNK):
        chunk = product_ids[i : i + STOCK_CHUNK]
        sql, params = sql_stock_chunk(chunk)
        for row in query_rows(sql, params):
            pid = _as_int(row.get("PRODUCT_ID"))
            if pid is None:
                continue
            stock_by_id[pid] = _as_decimal(row.get("CURRENT_STOCK"))

    window_start = snapshot_date - timedelta(days=365)
    sold_ids = set(
        SaleFact.objects.filter(sale_date__gte=window_start).values_list(
            "product__granit_id", flat=True
        )
    )

    snapshots: list[StockSnapshot] = []
    products = {p.granit_id: p for p in Product.objects.filter(granit_id__in=product_ids)}
    active_count = 0
    for pid, product in products.items():
        qty = stock_by_id.get(pid, Decimal("0"))
        is_active = qty != 0 or pid in sold_ids
        if product.is_active != is_active:
            product.is_active = is_active
            product.save(update_fields=["is_active", "updated_at"])
        if is_active:
            active_count += 1
        if qty == 0 and pid not in sold_ids:
            continue
        snapshots.append(
            StockSnapshot(
                snapshot_date=snapshot_date,
                store=store,
                product=product,
                quantity=qty,
            )
        )

    with transaction.atomic():
        StockSnapshot.objects.filter(snapshot_date=snapshot_date, store=store).delete()
        StockSnapshot.objects.bulk_create(snapshots, batch_size=1000)
    set_watermark("stock", snapshot_date)
    return {"rows": len(snapshots), "active": active_count}


def default_backfill_range() -> tuple[date, date]:
    yesterday = date.today() - timedelta(days=1)
    start = yesterday - timedelta(days=364)
    return start, yesterday + timedelta(days=1)
