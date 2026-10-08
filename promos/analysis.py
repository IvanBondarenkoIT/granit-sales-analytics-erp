from datetime import date, timedelta
from decimal import Decimal
from statistics import mean, median

from django.db.models import Sum

from core.models import Product, ProductGroup
from promos.models import Promo, PromoAnalysis, PromoProduct
from sales.models import SaleFact

FORECAST_RECENT_DAYS = 56
SEASONAL_WINDOW = 3
SEASONAL_CLAMP = (Decimal("0.3"), Decimal("3.0"))


def _shift_year(day: date, years: int = -1) -> date:
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return day.replace(year=day.year + years, day=28)


def _daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def target_product_ids(promo: Promo) -> list[int]:
    ids: set[int] = set()
    rows = promo.promo_products.all()
    group_ids = [row.product_group_id for row in rows if row.product_group_id]
    for row in rows:
        if row.product_id:
            ids.add(row.product_id)
    if group_ids:
        ids.update(Product.objects.filter(group_id__in=group_ids).values_list("id", flat=True))
    return list(ids)


def _daily_totals(product_ids: list[int], date_from: date, date_to: date) -> dict[date, Decimal]:
    if not product_ids or date_to < date_from:
        return {}
    rows = (
        SaleFact.objects.retail().filter(
            product_id__in=product_ids,
            sale_date__gte=date_from,
            sale_date__lte=date_to,
        )
        .values("sale_date")
        .annotate(amount=Sum("amount"))
    )
    return {row["sale_date"]: row["amount"] or Decimal("0") for row in rows}


def _warehouse_span() -> tuple[date | None, date | None]:
    dates = SaleFact.objects.order_by("sale_date").values_list("sale_date", flat=True)
    first = dates.first()
    last = SaleFact.objects.order_by("-sale_date").values_list("sale_date", flat=True).first()
    return first, last


def _window_values(
    daily: dict[date, Decimal],
    win_from: date,
    win_to: date,
    wh_min: date | None,
    wh_max: date | None,
) -> list[Decimal]:
    if wh_min is None or wh_max is None or win_to < win_from:
        return []
    values = []
    for day in _daterange(win_from, win_to):
        if wh_min <= day <= wh_max:
            values.append(daily.get(day, Decimal("0")))
    return values


def _weekly_totals(daily: dict[date, Decimal], hist_from: date, hist_to: date) -> dict[tuple[int, int], Decimal]:
    weeks: dict[tuple[int, int], Decimal] = {}
    for day in _daterange(hist_from, hist_to):
        iso = day.isocalendar()
        key = (iso.year, iso.week)
        weeks[key] = weeks.get(key, Decimal("0")) + daily.get(day, Decimal("0"))
    return weeks


def _seasonal_index(weekly_totals: dict[tuple[int, int], Decimal], iso_week: int) -> Decimal:
    values = list(weekly_totals.values())
    if not values:
        return Decimal("1")
    overall = median(values)
    if overall <= 0:
        return Decimal("1")
    lo, hi = iso_week - SEASONAL_WINDOW, iso_week + SEASONAL_WINDOW
    nearby = [
        total
        for (_year, week), total in weekly_totals.items()
        if lo <= week <= hi or week >= lo + 53 or week <= hi - 53
    ]
    if not nearby:
        return Decimal("1")
    idx = median(nearby) / overall
    low, high = SEASONAL_CLAMP
    if idx < low:
        return low
    if idx > high:
        return high
    return idx


def _mean2(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return (sum(values, Decimal("0")) / len(values)).quantize(Decimal("0.01"))


def analyze_promo(promo: Promo) -> int:
    product_ids = target_product_ids(promo)
    PromoAnalysis.objects.filter(promo=promo).delete()
    if not product_ids or promo.end_date < promo.start_date:
        return 0

    start, end = promo.start_date, promo.end_date
    pre_from = start - timedelta(days=promo.pre_period_days)
    pre_to = start - timedelta(days=1)
    recent_from = start - timedelta(days=FORECAST_RECENT_DAYS)
    yoy_from = _shift_year(start)
    yoy_to = _shift_year(end)
    wh_min, wh_max = _warehouse_span()

    fetch_from = min(pre_from, recent_from, yoy_from, start)
    if wh_min:
        fetch_from = min(fetch_from, wh_min)
    fetch_to = max(end, yoy_to)
    daily = _daily_totals(product_ids, fetch_from, fetch_to)

    pre_values = _window_values(daily, pre_from, pre_to, wh_min, wh_max)
    pre_mean = _mean2(pre_values)
    yoy_values = _window_values(daily, yoy_from, yoy_to, wh_min, wh_max)
    yoy_mean = _mean2(yoy_values)
    recent_values = _window_values(daily, recent_from, pre_to, wh_min, wh_max)
    recent_mean = mean(recent_values) if recent_values else Decimal("0")

    hist_from = wh_min or recent_from
    hist_to = pre_to
    weekly: dict[tuple[int, int], Decimal] = {}
    if hist_from <= hist_to:
        weekly = _weekly_totals(daily, hist_from, hist_to)

    rows = []
    for day in _daterange(start, end):
        idx = _seasonal_index(weekly, day.isocalendar().week)
        forecast = (recent_mean * idx).quantize(Decimal("0.01")) if recent_values else None
        rows.append(
            PromoAnalysis(
                promo=promo,
                analysis_date=day,
                actual_sales=daily.get(day, Decimal("0")),
                baseline_pre_period=pre_mean,
                baseline_yoy=yoy_mean,
                forecast_value=forecast,
            )
        )
    PromoAnalysis.objects.bulk_create(rows)
    return len(rows)


def import_promo_rows(
    rows,
    *,
    default_name: str = "",
    default_start: date | None = None,
    default_end: date | None = None,
    default_days: int = 14,
    default_notes: str = "",
) -> list[Promo]:
    from collections import OrderedDict

    from django.utils.translation import gettext as _

    buckets: OrderedDict[tuple, list] = OrderedDict()
    for row in rows:
        name = row.name or default_name
        start = row.start_date or default_start
        end = row.end_date or default_end
        if not name or not start or not end:
            raise ValueError(_("Each promo needs a name, start date, and end date."))
        if end < start:
            raise ValueError(_("Promo end must be on or after the start date."))
        buckets.setdefault((name, start, end), []).append(row)

    created: list[Promo] = []
    for (name, start, end), items in buckets.items():
        days = next((item.pre_period_days for item in items if item.pre_period_days), None) or default_days
        notes = next((item.notes for item in items if item.notes), "") or default_notes
        promo = Promo.objects.create(
            name=name,
            start_date=start,
            end_date=end,
            pre_period_days=days,
            notes=notes,
        )
        targets = []
        seen: set[tuple] = set()
        for item in items:
            if item.group_granit_id is not None:
                group = ProductGroup.objects.filter(granit_id=item.group_granit_id).first()
                if group is None:
                    promo.delete()
                    raise ValueError(_("Unknown product group ID: %(id)s") % {"id": item.group_granit_id})
                key = ("g", group.pk)
                if key not in seen:
                    seen.add(key)
                    targets.append(PromoProduct(promo=promo, product_group=group))
            if item.product_granit_id is not None:
                product = Product.objects.filter(granit_id=item.product_granit_id).first()
                if product is None:
                    promo.delete()
                    raise ValueError(_("Unknown product ID: %(id)s") % {"id": item.product_granit_id})
                key = ("p", product.pk)
                if key not in seen:
                    seen.add(key)
                    targets.append(PromoProduct(promo=promo, product=product))
        if not targets:
            promo.delete()
            raise ValueError(_("Each promo row needs group_id or product_id."))
        PromoProduct.objects.bulk_create(targets)
        analyze_promo(promo)
        created.append(promo)
    return created
