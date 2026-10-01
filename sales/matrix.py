"""Build super-group × store sales matrix with reconcile totals."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _

from core.models import ProductGroup, Store
from sales.models import SaleFact, SuperGroup, SuperGroupMember


ZERO = Decimal("0")


@dataclass
class Cell:
    qty: Decimal = ZERO
    amount: Decimal = ZERO

    def add(self, qty, amount) -> None:
        self.qty += qty or ZERO
        self.amount += amount or ZERO


@dataclass
class MatrixRow:
    super_group: SuperGroup | None
    key: str
    title: str
    color: str
    is_catchall: bool
    cells: dict[int, Cell] = field(default_factory=dict)  # store.pk -> Cell
    total: Cell = field(default_factory=Cell)
    ordered_cells: list = field(default_factory=list)

    def cell_for(self, store_pk: int) -> Cell:
        return self.cells.get(store_pk) or Cell()


@dataclass
class MatrixResult:
    date_from: date
    date_to: date
    stores: list[Store]
    rows: list[MatrixRow]
    column_totals: dict[int, Cell]
    ordered_column_totals: list
    grand: Cell
    fact_total: Cell
    balanced: bool
    period_query: str


def period_query(date_from: date, date_to: date, **extra) -> str:
    params = {"date_from": date_from.isoformat(), "date_to": date_to.isoformat()}
    params.update({k: v for k, v in extra.items() if v not in (None, "")})
    return urlencode(params)


def sales_in_period(date_from: date, date_to: date):
    return SaleFact.objects.filter(sale_date__gte=date_from, sale_date__lte=date_to)


def ensure_catchall() -> SuperGroup:
    sg, created = SuperGroup.objects.get_or_create(
        key="outside",
        defaults={
            "title": _("Outside super-groups"),
            "color": "FFFF00",
            "sort_order": 10_000,
            "is_catchall": True,
        },
    )
    if not sg.is_catchall:
        sg.is_catchall = True
        sg.sort_order = 10_000
        sg.save(update_fields=["is_catchall", "sort_order", "updated_at"])
    elif created:
        pass
    return sg


def build_matrix(date_from: date, date_to: date) -> MatrixResult:
    qs = sales_in_period(date_from, date_to)
    fact = qs.aggregate(
        qty=Coalesce(Sum("quantity"), ZERO),
        amount=Coalesce(Sum("amount"), ZERO),
    )
    fact_total = Cell(qty=fact["qty"] or ZERO, amount=fact["amount"] or ZERO)

    store_ids = list(qs.values_list("store_id", flat=True).distinct())
    stores = list(Store.objects.filter(id__in=store_ids).order_by("name"))

    member_map = {
        m.product_group_id: m.super_group_id
        for m in SuperGroupMember.objects.select_related("super_group")
    }
    super_groups = {
        sg.id: sg
        for sg in SuperGroup.objects.filter(is_catchall=False).order_by("sort_order", "title")
    }
    catchall = ensure_catchall()

    agg = (
        qs.values("store_id", "product__group_id")
        .annotate(qty=Sum("quantity"), amount=Sum("amount"))
    )

    rows_by_sg: dict[int | None, MatrixRow] = {}
    for sg in super_groups.values():
        rows_by_sg[sg.id] = MatrixRow(
            super_group=sg,
            key=sg.key,
            title=sg.title,
            color=sg.color,
            is_catchall=False,
        )
    rows_by_sg[None] = MatrixRow(
        super_group=catchall,
        key=catchall.key,
        title=catchall.title,
        color=catchall.color,
        is_catchall=True,
    )

    for row in agg:
        store_id = row["store_id"]
        group_id = row["product__group_id"]
        sg_id = member_map.get(group_id) if group_id is not None else None
        if sg_id not in rows_by_sg:
            sg_id = None
        target = rows_by_sg[sg_id]
        cell = target.cells.setdefault(store_id, Cell())
        cell.add(row["qty"], row["amount"])
        target.total.add(row["qty"], row["amount"])

    # Hide empty normal super-groups; always keep catchall if it has sales or any sales exist.
    visible: list[MatrixRow] = []
    for sg in super_groups.values():
        r = rows_by_sg[sg.id]
        if r.total.qty or r.total.amount:
            visible.append(r)
    catch = rows_by_sg[None]
    if catch.total.qty or catch.total.amount or not visible:
        visible.append(catch)

    column_totals: dict[int, Cell] = {s.id: Cell() for s in stores}
    grand = Cell()
    for r in visible:
        r.ordered_cells = [(store, r.cell_for(store.id)) for store in stores]
        for store, c in r.ordered_cells:
            column_totals[store.id].add(c.qty, c.amount)
        grand.add(r.total.qty, r.total.amount)

    ordered_column_totals = [(s, column_totals[s.id]) for s in stores]
    balanced = grand.qty == fact_total.qty and grand.amount == fact_total.amount
    return MatrixResult(
        date_from=date_from,
        date_to=date_to,
        stores=stores,
        rows=visible,
        column_totals=column_totals,
        ordered_column_totals=ordered_column_totals,
        grand=grand,
        fact_total=fact_total,
        balanced=balanced,
        period_query=period_query(date_from, date_to),
    )


def group_sales_for_super_group(
    super_group: SuperGroup,
    date_from: date,
    date_to: date,
    store_id: int | None = None,
) -> list[dict]:
    qs = sales_in_period(date_from, date_to)
    if store_id is not None:
        qs = qs.filter(store__granit_id=store_id)
    if super_group.is_catchall:
        member_group_ids = SuperGroupMember.objects.values_list("product_group_id", flat=True)
        qs = qs.exclude(product__group_id__in=member_group_ids)
        rows = (
            qs.values("product__group__granit_id", "product__group__name")
            .annotate(qty=Sum("quantity"), amount=Sum("amount"))
            .order_by("-amount")
        )
        return [
            {
                "granit_id": r["product__group__granit_id"],
                "name": r["product__group__name"] or _("(no group)"),
                "qty": r["qty"] or ZERO,
                "amount": r["amount"] or ZERO,
            }
            for r in rows
        ]

    members = list(
        SuperGroupMember.objects.filter(super_group=super_group).select_related("product_group")
    )
    member_group_ids = [m.product_group_id for m in members]
    sales_map = {
        r["product__group_id"]: r
        for r in qs.filter(product__group_id__in=member_group_ids)
        .values("product__group_id")
        .annotate(qty=Sum("quantity"), amount=Sum("amount"))
    }
    out = []
    for m in members:
        hit = sales_map.get(m.product_group_id) or {}
        out.append(
            {
                "granit_id": m.product_group.granit_id,
                "name": m.product_group.name,
                "qty": hit.get("qty") or ZERO,
                "amount": hit.get("amount") or ZERO,
            }
        )
    out.sort(key=lambda r: (-float(r["amount"]), r["name"]))
    return out


def product_sales_for_group(
    group_granit_id: int,
    date_from: date,
    date_to: date,
    store_id: int | None = None,
) -> list[dict]:
    qs = sales_in_period(date_from, date_to).filter(product__group__granit_id=group_granit_id)
    if store_id is not None:
        qs = qs.filter(store__granit_id=store_id)
    rows = (
        qs.values("product__granit_id", "product__name")
        .annotate(qty=Sum("quantity"), amount=Sum("amount"))
        .order_by("-amount")
    )
    return [
        {
            "granit_id": r["product__granit_id"],
            "name": r["product__name"],
            "qty": r["qty"] or ZERO,
            "amount": r["amount"] or ZERO,
        }
        for r in rows
    ]


def unassigned_groups(q: str = "", *, with_sales_only: bool = True, date_from=None, date_to=None):
    assigned = SuperGroupMember.objects.values_list("product_group_id", flat=True)
    qs = ProductGroup.objects.exclude(id__in=assigned)
    if q:
        qs = qs.filter(name__icontains=q)
    if with_sales_only and date_from and date_to:
        sold = (
            sales_in_period(date_from, date_to)
            .exclude(product__group_id=None)
            .values_list("product__group_id", flat=True)
            .distinct()
        )
        qs = qs.filter(id__in=sold)
    return qs.order_by("name")[:300]
