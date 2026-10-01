"""Server-side SVG geometry for promo comparison charts."""
from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils.formats import number_format

from promos.analysis import _daily_totals, _daterange, _shift_year, _warehouse_span, target_product_ids
from promos.models import Promo

POST_DAYS = 7
MAX_X_LABELS = 10

WIDTH = 800
LINE_HEIGHT = 260
PAD_LEFT = 64
PAD_RIGHT = 16
PAD_TOP = 16
PAD_BOTTOM = 32

BAR_ROW = 46
BAR_LABEL_W = 150
BAR_VALUE_W = 190


def fmt_money(value) -> str:
    if value is None:
        return "—"
    return f"{float(value):,.0f}".replace(",", "\u00a0")


def fmt_signed(value) -> str:
    if value is None:
        return "—"
    sign = "+" if value >= 0 else "−"
    return sign + fmt_money(abs(value))


def fmt_percent(value) -> str:
    """Signed percent with one decimal and the active locale's decimal separator."""
    sign = "+" if value >= 0 else "−"
    rounded = abs(Decimal(str(value))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return f"{sign}{number_format(rounded, decimal_pos=1, use_l10n=True)}%"


def lift_percent(actual: Decimal, baseline: Decimal | None) -> Decimal | None:
    if baseline is None or baseline == 0:
        return None
    return ((actual / baseline) - 1) * Decimal("100")


def _nice_ticks(max_value: float, count: int = 4) -> list[float]:
    if max_value <= 0:
        return [0.0, 1.0]
    raw = max_value / count
    magnitude = 10 ** math.floor(math.log10(raw))
    step = next(m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= raw)
    top = math.ceil(max_value / step) * step
    ticks = []
    value = 0.0
    while value <= top + step / 2:
        ticks.append(value)
        value += step
    return ticks


def _segments(points: list[tuple[float, float] | None]) -> list[str]:
    """Split a series into polyline strings at missing values."""
    out, current = [], []
    for point in points:
        if point is None:
            if len(current) > 1:
                out.append(" ".join(current))
            current = []
            continue
        current.append(f"{point[0]:.1f},{point[1]:.1f}")
    if len(current) > 1:
        out.append(" ".join(current))
    return out


class _Plot:
    def __init__(self, n: int, y_max: float, height: int = LINE_HEIGHT):
        self.n = n
        self.height = height
        self.plot_w = WIDTH - PAD_LEFT - PAD_RIGHT
        self.plot_h = height - PAD_TOP - PAD_BOTTOM
        self.ticks = _nice_ticks(y_max)
        self.top = self.ticks[-1] or 1.0
        self.step = self.plot_w / (n - 1) if n > 1 else self.plot_w

    def x(self, i: int) -> float:
        if self.n <= 1:
            return PAD_LEFT + self.plot_w / 2
        return PAD_LEFT + i * self.step

    def y(self, value) -> float:
        return PAD_TOP + self.plot_h * (1 - float(value) / self.top)

    @property
    def baseline_y(self) -> float:
        return PAD_TOP + self.plot_h

    def y_axis(self) -> list[dict]:
        return [{"y": round(self.y(t), 1), "label": fmt_money(t)} for t in self.ticks]


def _daily_chart(promo, product_ids, analyses, pre_median, wh_min, wh_max) -> dict:
    start, end = promo.start_date, promo.end_date
    window_from = start - timedelta(days=promo.pre_period_days)
    window_to = end + timedelta(days=POST_DAYS)
    if wh_max is not None:
        window_to = max(end, min(window_to, wh_max))
    days = list(_daterange(window_from, window_to))

    actual_daily = _daily_totals(product_ids, window_from, window_to)
    ly_from, ly_to = _shift_year(window_from), _shift_year(window_to)
    ly_daily = _daily_totals(product_ids, ly_from, ly_to)
    forecast = {row.analysis_date: row.forecast_value for row in analyses}

    def in_span(day: date) -> bool:
        return wh_min is not None and wh_max is not None and wh_min <= day <= wh_max

    actual = [actual_daily.get(d, Decimal("0")) if in_span(d) else None for d in days]
    last_year = []
    for d in days:
        ly_day = _shift_year(d)
        last_year.append(ly_daily.get(ly_day, Decimal("0")) if in_span(ly_day) else None)
    has_last_year = any(v for v in last_year if v is not None)
    if not has_last_year:
        last_year = [None] * len(days)
    fc = [forecast.get(d) if start <= d <= end else None for d in days]

    values = [float(v) for series in (actual, last_year, fc) for v in series if v is not None]
    if pre_median is not None:
        values.append(float(pre_median))
    plot = _Plot(len(days), max(values or [0.0]))

    def pts(series):
        return [None if v is None else (plot.x(i), plot.y(v)) for i, v in enumerate(series)]

    i_start = days.index(start)
    i_end = days.index(end)
    half = plot.step / 2 if plot.n > 1 else plot.plot_w / 2
    band_x1 = max(PAD_LEFT, plot.x(i_start) - half)
    band_x2 = min(WIDTH - PAD_RIGHT, plot.x(i_end) + half)

    label_every = max(1, math.ceil(len(days) / MAX_X_LABELS))
    x_labels = [
        {"x": round(plot.x(i), 1), "label": d.strftime("%d.%m")}
        for i, d in enumerate(days)
        if i % label_every == 0 or i == len(days) - 1
    ]
    dots = [
        {
            "x": round(plot.x(i), 1),
            "y": round(plot.y(v), 1),
            "title": f"{d.strftime('%d.%m.%Y')}: {fmt_money(v)}",
            "promo": start <= d <= end,
        }
        for i, (d, v) in enumerate(zip(days, actual))
        if v is not None
    ]
    return {
        "width": WIDTH,
        "height": plot.height,
        "pad_left": PAD_LEFT,
        "pad_right_x": WIDTH - PAD_RIGHT,
        "axis_y": round(plot.baseline_y, 1),
        "y_axis": plot.y_axis(),
        "x_labels": x_labels,
        "band": {"x": round(band_x1, 1), "w": round(band_x2 - band_x1, 1), "y": PAD_TOP, "h": round(plot.plot_h, 1)},
        "actual": _segments(pts(actual)),
        "last_year": _segments(pts(last_year)),
        "forecast": _segments(pts(fc)),
        "baseline_y": round(plot.y(pre_median), 1) if pre_median is not None else None,
        "dots": dots,
        "has_last_year": has_last_year,
        "has_forecast": any(v is not None for v in fc),
        "has_baseline": pre_median is not None,
        "n_days": len(days),
        "series": {"days": days, "actual": actual, "last_year": last_year, "forecast": fc},
    }


def _bars_chart(actual_sum, baseline_sum, yoy_sum, forecast_sum, labels) -> dict:
    items = [
        ("actual", labels["actual"], actual_sum),
        ("baseline", labels["baseline"], baseline_sum),
        ("yoy", labels["yoy"], yoy_sum),
        ("forecast", labels["forecast"], forecast_sum),
    ]
    max_value = max([float(v) for _k, _l, v in items if v is not None] or [1.0]) or 1.0
    bar_max = WIDTH - BAR_LABEL_W - BAR_VALUE_W
    rows = []
    for idx, (key, label, value) in enumerate(items):
        y = 8 + idx * BAR_ROW
        lift = lift_percent(actual_sum, value) if key != "actual" else None
        width = bar_max * float(value) / max_value if value is not None else 0
        rows.append(
            {
                "key": key,
                "label": label,
                "y": y,
                "text_y": y + 19,
                "bar_x": BAR_LABEL_W,
                "bar_w": round(max(width, 2 if value else 0), 1),
                "value_x": round(BAR_LABEL_W + max(width, 0) + 8, 1),
                "lift_x": WIDTH - 96,
                "value": fmt_money(value) if value is not None else None,
                "lift": lift,
                "lift_text": fmt_percent(lift) if lift is not None else "",
            }
        )
    return {"width": WIDTH, "height": 8 + len(items) * BAR_ROW, "rows": rows, "bar_h": 28}


def _cumulative_chart(analyses, pre_median) -> dict | None:
    if not analyses or pre_median is None:
        return None
    cum_actual, cum_base = [], []
    run_a = Decimal("0")
    for i, row in enumerate(analyses, start=1):
        run_a += row.actual_sales
        cum_actual.append(run_a)
        cum_base.append(pre_median * i)
    # leading zero so both lines start at the origin
    cum_actual.insert(0, Decimal("0"))
    cum_base.insert(0, Decimal("0"))
    plot = _Plot(len(cum_actual), max(float(max(cum_actual)), float(max(cum_base))), height=220)
    a_pts = [(plot.x(i), plot.y(v)) for i, v in enumerate(cum_actual)]
    b_pts = [(plot.x(i), plot.y(v)) for i, v in enumerate(cum_base)]
    area = " ".join(f"{x:.1f},{y:.1f}" for x, y in a_pts + list(reversed(b_pts)))
    final_actual, final_base = cum_actual[-1], cum_base[-1]
    diff = final_actual - final_base
    lift = lift_percent(final_actual, final_base)
    days = [None] + [row.analysis_date for row in analyses]
    label_every = max(1, math.ceil(len(days) / MAX_X_LABELS))
    x_labels = [
        {"x": round(plot.x(i), 1), "label": d.strftime("%d.%m")}
        for i, d in enumerate(days)
        if d is not None and (i % label_every == 0 or i == len(days) - 1)
    ]
    return {
        "width": WIDTH,
        "height": plot.height,
        "pad_left": PAD_LEFT,
        "pad_right_x": WIDTH - PAD_RIGHT,
        "axis_y": round(plot.baseline_y, 1),
        "y_axis": plot.y_axis(),
        "x_labels": x_labels,
        "actual": _segments(a_pts),
        "baseline": _segments(b_pts),
        "area": area,
        "positive": diff >= 0,
        "end_x": round(a_pts[-1][0], 1),
        "end_y": round(min(a_pts[-1][1], b_pts[-1][1]) - 8, 1),
        "label": f"{fmt_signed(diff)} ({fmt_percent(lift or 0)})",
        "diff": diff,
        "final_actual": final_actual,
        "final_base": final_base,
    }


def build_promo_charts(promo: Promo, labels: dict[str, str]) -> dict:
    analyses = list(promo.analyses.order_by("analysis_date"))
    if not analyses:
        return {"empty": True}
    n_days = len(analyses)
    pre_median = analyses[0].baseline_pre_period
    yoy_median = analyses[0].baseline_yoy
    actual_sum = sum((row.actual_sales for row in analyses), Decimal("0"))
    baseline_sum = pre_median * n_days if pre_median is not None else None
    yoy_sum = yoy_median * n_days if yoy_median is not None else None
    has_forecast = any(row.forecast_value is not None for row in analyses)
    forecast_sum = (
        sum((row.forecast_value or Decimal("0") for row in analyses), Decimal("0")) if has_forecast else None
    )
    best = max(analyses, key=lambda row: row.actual_sales)
    incremental = actual_sum - baseline_sum if baseline_sum is not None else None

    product_ids = target_product_ids(promo)
    wh_min, wh_max = _warehouse_span()
    return {
        "empty": False,
        "kpi": {
            "incremental": incremental,
            "incremental_text": fmt_signed(incremental),
            "lift_pre": lift_percent(actual_sum, baseline_sum),
            "lift_yoy": lift_percent(actual_sum, yoy_sum),
            "best_day": best.analysis_date,
            "best_amount": fmt_money(best.actual_sales),
            "actual_sum": actual_sum,
            "baseline_sum": baseline_sum,
        },
        "daily": _daily_chart(promo, product_ids, analyses, pre_median, wh_min, wh_max),
        "bars": _bars_chart(actual_sum, baseline_sum, yoy_sum, forecast_sum, labels),
        "cumulative": _cumulative_chart(analyses, pre_median),
    }
