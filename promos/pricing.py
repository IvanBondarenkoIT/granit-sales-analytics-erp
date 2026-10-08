"""Per-SKU price / stock / earnings rows for a promo card."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Sum

from core.models import GranitWpMapping, Product, ProductCostSnapshot, SiteProduct
from promos.analysis import target_product_ids
from promos.models import Promo, PromoProduct
from sales.models import SaleFact

PRICE_DIFF_THRESHOLD = Decimal("0.01")  # 1%


@dataclass
class PromoPriceRow:
    product: Product
    site_name: str | None
    last_cost: Decimal | None
    avg_cost_90d: Decimal | None
    stock_qty: Decimal
    retail_price: Decimal | None
    sale_price: Decimal | None
    retail_compare: Decimal | None  # site or fact shown in parentheses
    sale_compare: Decimal | None
    margin_pct: Decimal | None
    estimated_earnings: Decimal | None
    has_site_link: bool


def _pct_diff(a: Decimal | None, b: Decimal | None) -> bool:
    if a is None or b is None or a == 0:
        return a != b and a is not None and b is not None
    return abs(a - b) / abs(a) > PRICE_DIFF_THRESHOLD


def _avg_sold_unit_price(product_id: int, date_from: date, date_to: date) -> Decimal | None:
    agg = (
        SaleFact.objects.retail()
        .filter(product_id=product_id, sale_date__gte=date_from, sale_date__lte=date_to)
        .aggregate(qty=Sum("quantity"), amount=Sum("amount"))
    )
    qty = agg["qty"] or Decimal("0")
    amount = agg["amount"] or Decimal("0")
    if qty <= 0:
        return None
    return (amount / qty).quantize(Decimal("0.01"))


def _latest_costs(product_ids: list[int]) -> dict[int, ProductCostSnapshot]:
    if not product_ids:
        return {}
    by_id: dict[int, ProductCostSnapshot] = {}
    for row in ProductCostSnapshot.objects.filter(product_id__in=product_ids).order_by(
        "-snapshot_date"
    ):
        by_id.setdefault(row.product_id, row)
    return by_id

def build_promo_price_rows(promo: Promo) -> list[PromoPriceRow]:
    product_ids = target_product_ids(promo)
    if not product_ids:
        return []
    products = {p.id: p for p in Product.objects.filter(id__in=product_ids)}
    costs = _latest_costs(product_ids)

    granit_ids = [p.granit_id for p in products.values()]
    mapping = {
        m.granit_id: m.wp_product_id
        for m in GranitWpMapping.objects.filter(granit_id__in=granit_ids)
    }
    site_by_wp = {
        s.wp_product_id: s
        for s in SiteProduct.objects.filter(wp_product_id__in=mapping.values())
    }
    manual = {
        row.product_id: row.manual_sale_price
        for row in PromoProduct.objects.filter(promo=promo, product_id__in=product_ids)
        if row.manual_sale_price is not None
    }

    rows: list[PromoPriceRow] = []
    for pid in sorted(product_ids, key=lambda i: products[i].name.lower()):
        product = products[pid]
        cost = costs.get(pid)
        last_cost = cost.last_cost if cost else None
        avg_cost = cost.avg_cost_90d if cost else None
        stock = cost.stock_qty if cost else Decimal("0")

        wp_id = mapping.get(product.granit_id)
        site = site_by_wp.get(wp_id) if wp_id else None
        site_regular = site.regular_price if site else None
        site_sale = site.effective_sale_price if site else None
        if pid in manual:
            sale_price = manual[pid]
        else:
            sale_price = site_sale
        retail = site_regular

        fact_avg = _avg_sold_unit_price(pid, promo.start_date, promo.end_date)
        retail_compare = None
        sale_compare = None
        # Site is the promo price list; Granit sold avg in parentheses when it differs.
        if _pct_diff(sale_price, fact_avg):
            sale_compare = fact_avg
        if _pct_diff(retail, fact_avg) and sale_price != retail:
            # only show retail compare if no sale compare already covering fact
            if sale_compare is None and retail is not None:
                retail_compare = fact_avg

        margin = None
        earnings = None
        if sale_price is not None and last_cost is not None and sale_price != 0:
            margin = ((sale_price - last_cost) / sale_price * Decimal("100")).quantize(
                Decimal("0.1")
            )
            earnings = ((sale_price - last_cost) * stock).quantize(Decimal("0.01"))

        rows.append(
            PromoPriceRow(
                product=product,
                site_name=site.name if site else None,
                last_cost=last_cost,
                avg_cost_90d=avg_cost,
                stock_qty=stock,
                retail_price=retail,
                sale_price=sale_price,
                retail_compare=retail_compare,
                sale_compare=sale_compare,
                margin_pct=margin,
                estimated_earnings=earnings,
                has_site_link=bool(site),
            )
        )
    return rows


def promo_estimated_earnings_total(promo: Promo) -> Decimal | None:
    rows = build_promo_price_rows(promo)
    values = [r.estimated_earnings for r in rows if r.estimated_earnings is not None]
    if not values:
        return None
    return sum(values, Decimal("0"))
