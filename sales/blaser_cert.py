"""One-off: Blaser pack buyers at ~10% off (certificate redemption proxy)."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Iterable

from openpyxl import Workbook

from core.models import Client
from sales.models import SOURCE_INVOICE, SOURCE_RECEIPT, SaleFact, SuperGroupMember

# Blasercafe blend packs (not single origin).
BLASER_GROUP_IDS = (11077, 16279)
LOYALTY_CARD_GROUP_ID = 24303
COFFEE_MAKERS_KEY = "coffee_makers"
# Machines: receipts + invoices (not realized — same retail lines by warehouse date).
MACHINE_SOURCES = (SOURCE_RECEIPT, SOURCE_INVOICE)

PRICE_STEP = Decimal("0.01")
DISCOUNT_RATIO = Decimal("0.9")
# Relative tolerance vs expected promo / full price.
PRICE_TOLERANCE = Decimal("0.03")
CARD_RE = re.compile(r"^\d{13}$")


def _q(value: Decimal) -> Decimal:
    return value.quantize(PRICE_STEP, rounding=ROUND_HALF_UP)


def unit_price(amount: Decimal, quantity: Decimal) -> Decimal | None:
    if quantity <= 0:
        return None
    return _q(amount / quantity)


@dataclass
class SkuCalibration:
    product_id: int
    granit_id: int
    name: str
    group_id: int
    group_name: str
    full_price: Decimal | None
    expected_10: Decimal | None
    count_full: int = 0
    count_10: int = 0
    count_other: int = 0
    sample_prices: tuple[tuple[Decimal, int], ...] = ()


@dataclass
class PromoLine:
    client_id: int
    sale_date: date
    granit_sale_id: int
    product_id: int
    product_name: str
    store_name: str
    quantity: Decimal
    amount: Decimal
    unit_price: Decimal


@dataclass
class MachineLine:
    client_id: int
    sale_date: date
    product_id: int
    product_name: str
    store_name: str
    amount: Decimal
    granit_sale_id: int


@dataclass
class ClientPromoRow:
    client_id: int
    granit_id: int
    name: str
    phone: str
    card_number: str
    visits: int
    amount_at_10: Decimal
    first_promo_date: date
    last_promo_date: date
    machine_count: int = 0
    machine_first_date: date | None = None
    machine_last_date: date | None = None
    machines: str = ""


@dataclass
class MachineCrossRow:
    client_id: int
    granit_id: int
    name: str
    phone: str
    card_number: str
    machine_first_date: date
    machine_last_date: date
    machines: str
    used_promo_10: bool
    promo_visits: int


@dataclass
class LoyaltyLine:
    sale_date: date
    client_granit_id: int | None
    product_granit_id: int
    product_name: str
    store_name: str
    quantity: Decimal
    amount: Decimal


@dataclass
class BlaserCertReport:
    date_from: date
    date_to: date  # exclusive
    calibrations: list[SkuCalibration]
    clients: list[ClientPromoRow]
    machines_detail: list[MachineLine]
    machine_cross: list[MachineCrossRow]
    loyalty_cards: list[LoyaltyLine]
    summary: dict = field(default_factory=dict)


def calibrate_full_price(prices: Iterable[Decimal]) -> Decimal | None:
    """Pick list price: highest frequent price that pairs with ~10% mode, else mode."""
    rounded = [_q(p) for p in prices]
    if not rounded:
        return None
    counts = Counter(rounded)
    top = counts.most_common(8)
    mode_price, mode_n = top[0]
    full = mode_price
    for price, n in top[1:]:
        if n < max(2, int(mode_n * 0.25)):
            continue
        higher, lower = (price, mode_price) if price > mode_price else (mode_price, price)
        if higher <= 0:
            continue
        ratio = lower / higher
        if abs(ratio - DISCOUNT_RATIO) <= Decimal("0.05"):
            full = higher
            break
    else:
        # No clear pair: prefer the highest price among those with decent volume.
        min_n = max(2, len(rounded) // 25)
        frequent = [p for p, c in counts.items() if c >= min_n] or [mode_price]
        full = max(frequent)
    return full


def classify_price(unit: Decimal, full: Decimal) -> str:
    expected = _q(full * DISCOUNT_RATIO)
    if full <= 0:
        return "other"
    if abs(unit - full) / full <= PRICE_TOLERANCE:
        return "full"
    if abs(unit - expected) / expected <= PRICE_TOLERANCE:
        return "promo_10"
    return "other"


def _coffee_maker_group_ids() -> set[int]:
    return set(
        SuperGroupMember.objects.filter(super_group__key=COFFEE_MAKERS_KEY).values_list(
            "product_group_id", flat=True
        )
    )


def build_report(date_from: date, date_to: date) -> BlaserCertReport:
    """Analyze retail Blaser lines in [date_from, date_to)."""
    blaser_qs = (
        SaleFact.objects.retail()
        .filter(
            sale_date__gte=date_from,
            sale_date__lt=date_to,
            product__group__granit_id__in=BLASER_GROUP_IDS,
            quantity__gt=0,
        )
        .select_related("product", "product__group", "store", "client")
    )

    by_product: dict[int, list[Decimal]] = defaultdict(list)
    line_rows: list[tuple[SaleFact, Decimal]] = []
    for fact in blaser_qs.iterator(chunk_size=2000):
        up = unit_price(fact.amount, fact.quantity)
        if up is None:
            continue
        by_product[fact.product_id].append(up)
        line_rows.append((fact, up))

    product_meta: dict[int, tuple[int, str, int, str]] = {}
    for fact, _up in line_rows:
        if fact.product_id in product_meta:
            continue
        group = fact.product.group
        product_meta[fact.product_id] = (
            fact.product.granit_id,
            fact.product.name,
            group.granit_id if group else 0,
            group.name if group else "",
        )

    calibrations: list[SkuCalibration] = []
    full_by_product: dict[int, Decimal] = {}
    cal_by_product: dict[int, SkuCalibration] = {}
    for product_id, prices in by_product.items():
        meta = product_meta.get(product_id)
        if meta is None:
            continue
        granit_id, name, group_gid, group_name = meta
        full = calibrate_full_price(prices)
        expected = _q(full * DISCOUNT_RATIO) if full else None
        if full:
            full_by_product[product_id] = full
        counts = Counter(prices)
        cal = SkuCalibration(
            product_id=product_id,
            granit_id=granit_id,
            name=name,
            group_id=group_gid,
            group_name=group_name,
            full_price=full,
            expected_10=expected,
            sample_prices=tuple(counts.most_common(8)),
        )
        cal_by_product[product_id] = cal
        calibrations.append(cal)

    promo_lines: list[PromoLine] = []
    for fact, up in line_rows:
        full = full_by_product.get(fact.product_id)
        kind = classify_price(up, full) if full is not None else "other"
        cal = cal_by_product[fact.product_id]
        if kind == "full":
            cal.count_full += 1
        elif kind == "promo_10":
            cal.count_10 += 1
            if fact.client_id:
                promo_lines.append(
                    PromoLine(
                        client_id=fact.client_id,
                        sale_date=fact.sale_date,
                        granit_sale_id=fact.granit_sale_id,
                        product_id=fact.product.granit_id,
                        product_name=fact.product.name,
                        store_name=fact.store.name,
                        quantity=fact.quantity,
                        amount=fact.amount,
                        unit_price=up,
                    )
                )
        else:
            cal.count_other += 1

    calibrations.sort(key=lambda c: (-(c.count_full + c.count_10 + c.count_other), c.name))

    by_client_lines: dict[int, list[PromoLine]] = defaultdict(list)
    for line in promo_lines:
        by_client_lines[line.client_id].append(line)

    client_ids = list(by_client_lines.keys())
    clients_map = {
        c.id: c
        for c in Client.objects.filter(id__in=client_ids).only(
            "id", "granit_id", "name", "phone", "card_number"
        )
    }

    maker_group_ids = _coffee_maker_group_ids()
    machines_by_client: dict[int, list[MachineLine]] = defaultdict(list)
    if maker_group_ids and client_ids:
        machine_qs = (
            SaleFact.objects.filter(
                source__in=MACHINE_SOURCES,
                client_id__in=client_ids,
                product__group_id__in=maker_group_ids,
                quantity__gt=0,
            )
            .select_related("product", "store")
            .order_by("sale_date", "id")
        )
        for fact in machine_qs.iterator(chunk_size=2000):
            machines_by_client[fact.client_id].append(
                MachineLine(
                    client_id=fact.client_id,
                    sale_date=fact.sale_date,
                    product_id=fact.product.granit_id,
                    product_name=fact.product.name,
                    store_name=fact.store.name,
                    amount=fact.amount,
                    granit_sale_id=fact.granit_sale_id,
                )
            )

    client_rows: list[ClientPromoRow] = []
    machines_detail: list[MachineLine] = []
    for cid, lines in by_client_lines.items():
        client = clients_map.get(cid)
        if client is None:
            continue
        visit_keys = {(ln.sale_date, ln.granit_sale_id) for ln in lines}
        visits = len(visit_keys)
        amounts = sum((ln.amount for ln in lines), Decimal("0"))
        dates = [ln.sale_date for ln in lines]
        machines = machines_by_client.get(cid, [])
        machines_detail.extend(machines)
        machines_text = "; ".join(
            f"{m.sale_date.isoformat()}: {m.product_name} ({m.store_name})" for m in machines
        )
        client_rows.append(
            ClientPromoRow(
                client_id=cid,
                granit_id=client.granit_id,
                name=client.name or "",
                phone=(client.phone or "").strip(),
                card_number=(client.card_number or "").strip(),
                visits=visits,
                amount_at_10=_q(amounts),
                first_promo_date=min(dates),
                last_promo_date=max(dates),
                machine_count=len(machines),
                machine_first_date=machines[0].sale_date if machines else None,
                machine_last_date=machines[-1].sale_date if machines else None,
                machines=machines_text,
            )
        )
    client_rows.sort(key=lambda r: (-r.visits, -r.amount_at_10, r.granit_id))

    # Machine buyers in window × whether they used promo Blaser.
    machine_cross: list[MachineCrossRow] = []
    if maker_group_ids:
        window_makers = (
            SaleFact.objects.filter(
                source__in=MACHINE_SOURCES,
                sale_date__gte=date_from,
                sale_date__lt=date_to,
                product__group_id__in=maker_group_ids,
                quantity__gt=0,
                client_id__isnull=False,
            )
            .select_related("product", "store", "client")
            .order_by("sale_date", "id")
        )
        maker_lines: dict[int, list[MachineLine]] = defaultdict(list)
        for fact in window_makers.iterator(chunk_size=2000):
            maker_lines[fact.client_id].append(
                MachineLine(
                    client_id=fact.client_id,
                    sale_date=fact.sale_date,
                    product_id=fact.product.granit_id,
                    product_name=fact.product.name,
                    store_name=fact.store.name,
                    amount=fact.amount,
                    granit_sale_id=fact.granit_sale_id,
                )
            )
        promo_visits = {r.client_id: r.visits for r in client_rows}
        cross_clients = {
            c.id: c
            for c in Client.objects.filter(id__in=maker_lines.keys()).only(
                "id", "granit_id", "name", "phone", "card_number"
            )
        }
        for cid, lines in maker_lines.items():
            client = cross_clients.get(cid)
            if client is None:
                continue
            text = "; ".join(
                f"{m.sale_date.isoformat()}: {m.product_name} ({m.store_name})" for m in lines
            )
            visits = promo_visits.get(cid, 0)
            machine_cross.append(
                MachineCrossRow(
                    client_id=cid,
                    granit_id=client.granit_id,
                    name=client.name or "",
                    phone=(client.phone or "").strip(),
                    card_number=(client.card_number or "").strip(),
                    machine_first_date=lines[0].sale_date,
                    machine_last_date=lines[-1].sale_date,
                    machines=text,
                    used_promo_10=visits > 0,
                    promo_visits=visits,
                )
            )
        machine_cross.sort(key=lambda r: (r.used_promo_10, r.machine_first_date, r.granit_id))

    loyalty_cards: list[LoyaltyLine] = []
    loyalty_qs = (
        SaleFact.objects.retail()
        .filter(
            sale_date__gte=date_from,
            sale_date__lt=date_to,
            product__group__granit_id=LOYALTY_CARD_GROUP_ID,
        )
        .select_related("product", "store", "client")
        .order_by("sale_date")
    )
    for fact in loyalty_qs.iterator(chunk_size=500):
        loyalty_cards.append(
            LoyaltyLine(
                sale_date=fact.sale_date,
                client_granit_id=fact.client.granit_id if fact.client_id else None,
                product_granit_id=fact.product.granit_id,
                product_name=fact.product.name,
                store_name=fact.store.name,
                quantity=fact.quantity,
                amount=fact.amount,
            )
        )

    n = len(client_rows)
    once = sum(1 for r in client_rows if r.visits == 1)
    multi = sum(1 for r in client_rows if r.visits > 1)
    with_phone = sum(1 for r in client_rows if r.phone)
    with_card = sum(1 for r in client_rows if CARD_RE.match(r.card_number))
    with_contact = sum(1 for r in client_rows if r.phone or CARD_RE.match(r.card_number))
    with_machine = sum(1 for r in client_rows if r.machine_count)
    makers_n = len(machine_cross)
    makers_used = sum(1 for r in machine_cross if r.used_promo_10)

    summary = {
        "date_from": date_from.isoformat(),
        "date_to_exclusive": date_to.isoformat(),
        "promo_clients": n,
        "visits_once": once,
        "visits_once_pct": round(100.0 * once / n, 1) if n else 0.0,
        "visits_multi": multi,
        "visits_multi_pct": round(100.0 * multi / n, 1) if n else 0.0,
        "with_phone": with_phone,
        "with_card": with_card,
        "with_contact": with_contact,
        "promo_with_coffee_maker": with_machine,
        "machine_buyers_in_window": makers_n,
        "machine_buyers_used_promo": makers_used,
        "machine_buyers_used_promo_pct": round(100.0 * makers_used / makers_n, 1) if makers_n else 0.0,
        "loyalty_card_lines": len(loyalty_cards),
        "blaser_lines_classified": sum(
            c.count_full + c.count_10 + c.count_other for c in calibrations
        ),
        "blaser_lines_promo_10": sum(c.count_10 for c in calibrations),
        "blaser_lines_full": sum(c.count_full for c in calibrations),
        "blaser_lines_other": sum(c.count_other for c in calibrations),
    }

    return BlaserCertReport(
        date_from=date_from,
        date_to=date_to,
        calibrations=calibrations,
        clients=client_rows,
        machines_detail=machines_detail,
        machine_cross=machine_cross,
        loyalty_cards=loyalty_cards,
        summary=summary,
    )


def _write_kv(ws, rows: list[tuple[str, object]]) -> None:
    ws.append(["metric", "value"])
    for key, value in rows:
        ws.append([key, value])


def write_report_xlsx(report: BlaserCertReport, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb = Workbook()

    ws = wb.active
    ws.title = "summary"
    s = report.summary
    _write_kv(
        ws,
        [
            ("date_from", s["date_from"]),
            ("date_to_exclusive", s["date_to_exclusive"]),
            ("promo_clients", s["promo_clients"]),
            ("visits_once", s["visits_once"]),
            ("visits_once_pct", s["visits_once_pct"]),
            ("visits_multi", s["visits_multi"]),
            ("visits_multi_pct", s["visits_multi_pct"]),
            ("with_phone", s["with_phone"]),
            ("with_card", s["with_card"]),
            ("with_contact", s["with_contact"]),
            ("promo_with_coffee_maker", s["promo_with_coffee_maker"]),
            ("machine_buyers_in_window", s["machine_buyers_in_window"]),
            ("machine_buyers_used_promo", s["machine_buyers_used_promo"]),
            ("machine_buyers_used_promo_pct", s["machine_buyers_used_promo_pct"]),
            ("machine_sources", "receipt+invoice (not realized)"),
            ("loyalty_card_lines", s["loyalty_card_lines"]),
            ("blaser_lines_classified", s["blaser_lines_classified"]),
            ("blaser_lines_full", s["blaser_lines_full"]),
            ("blaser_lines_promo_10", s["blaser_lines_promo_10"]),
            ("blaser_lines_other", s["blaser_lines_other"]),
            ("groups", ",".join(str(g) for g in BLASER_GROUP_IDS)),
            ("discount_ratio", str(DISCOUNT_RATIO)),
            ("price_tolerance", str(PRICE_TOLERANCE)),
        ],
    )

    cal = wb.create_sheet("price_calibration")
    cal.append(
        [
            "product_granit_id",
            "name",
            "group_id",
            "group_name",
            "full_price",
            "expected_10",
            "count_full",
            "count_10",
            "count_other",
            "top_prices",
        ]
    )
    for c in report.calibrations:
        top = "; ".join(f"{p}×{n}" for p, n in c.sample_prices)
        cal.append(
            [
                c.granit_id,
                c.name,
                c.group_id,
                c.group_name,
                float(c.full_price) if c.full_price is not None else None,
                float(c.expected_10) if c.expected_10 is not None else None,
                c.count_full,
                c.count_10,
                c.count_other,
                top,
            ]
        )

    clients = wb.create_sheet("clients")
    clients.append(
        [
            "granit_id",
            "name",
            "phone",
            "card_number",
            "visits",
            "amount_at_10",
            "first_promo_date",
            "last_promo_date",
            "machine_count",
            "machine_first_date",
            "machine_last_date",
            "machines",
        ]
    )
    for r in report.clients:
        clients.append(
            [
                r.granit_id,
                r.name,
                r.phone,
                r.card_number,
                r.visits,
                float(r.amount_at_10),
                r.first_promo_date.isoformat(),
                r.last_promo_date.isoformat(),
                r.machine_count,
                r.machine_first_date.isoformat() if r.machine_first_date else "",
                r.machine_last_date.isoformat() if r.machine_last_date else "",
                r.machines,
            ]
        )

    detail = wb.create_sheet("machines_detail")
    detail.append(
        ["client_granit_id", "sale_date", "product_id", "product_name", "store", "amount", "granit_sale_id"]
    )
    client_granit = {r.client_id: r.granit_id for r in report.clients}
    for m in report.machines_detail:
        detail.append(
            [
                client_granit.get(m.client_id, ""),
                m.sale_date.isoformat(),
                m.product_id,
                m.product_name,
                m.store_name,
                float(m.amount),
                m.granit_sale_id,
            ]
        )

    sms = wb.create_sheet("sms_ready")
    sms.append(["customer_id", "phone"])
    for r in report.clients:
        if r.phone:
            sms.append([r.granit_id, r.phone])

    tg = wb.create_sheet("tg_ready")
    tg.append(["card", "phone"])
    for r in report.clients:
        if CARD_RE.match(r.card_number) and r.phone:
            tg.append([r.card_number, r.phone])

    cross = wb.create_sheet("machine_cross")
    cross.append(
        [
            "granit_id",
            "name",
            "phone",
            "card_number",
            "machine_first_date",
            "machine_last_date",
            "machines",
            "used_promo_10",
            "promo_visits",
        ]
    )
    for r in report.machine_cross:
        cross.append(
            [
                r.granit_id,
                r.name,
                r.phone,
                r.card_number,
                r.machine_first_date.isoformat(),
                r.machine_last_date.isoformat(),
                r.machines,
                "yes" if r.used_promo_10 else "no",
                r.promo_visits,
            ]
        )

    loy = wb.create_sheet("loyalty_cards")
    loy.append(
        [
            "sale_date",
            "client_granit_id",
            "product_granit_id",
            "product_name",
            "store",
            "quantity",
            "amount",
        ]
    )
    for row in report.loyalty_cards:
        loy.append(
            [
                row.sale_date.isoformat(),
                row.client_granit_id or "",
                row.product_granit_id,
                row.product_name,
                row.store_name,
                float(row.quantity),
                float(row.amount),
            ]
        )

    wb.save(path)
    return path
