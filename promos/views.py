import subprocess
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.models import GranitWpMapping, SiteProduct
from etl.pipeline import CATALOG_RUN_TYPE, catalog_sync_running, last_catalog_run, start_run
from promos.analysis import analyze_promo, import_promo_rows, target_product_ids
from promos.excel import DOCS_PROMOS_XLSX, LOCAL_PROMOS_XLSX, ensure_example_files, parse_promo_xlsx
from promos.forms import PromoForm
from promos.models import Promo, PromoProduct
from promos.pricing import build_promo_price_rows, promo_estimated_earnings_total


def catalog_status() -> dict:
    run = last_catalog_run()
    return {
        "run": run,
        "running": catalog_sync_running(),
        "site_products": SiteProduct.objects.count(),
        "mappings": GranitWpMapping.objects.count(),
    }


@require_POST
def promo_sync_catalog(request):
    if not request.user.is_staff:
        raise PermissionDenied
    if catalog_sync_running():
        messages.info(request, _("Catalog sync is already running."))
    else:
        run = start_run(CATALOG_RUN_TYPE)
        subprocess.Popen(
            [
                sys.executable,
                str(Path(settings.BASE_DIR) / "manage.py"),
                "sync_catalog",
                "--run-id",
                str(run.pk),
            ],
            cwd=settings.BASE_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        messages.success(request, _("Catalog sync started. Refresh the page in a few minutes."))
    next_url = request.POST.get("next") or ""
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        next_url = reverse("promo_list")
    return redirect(next_url)


def _lift(actual: Decimal, baseline: Decimal | None) -> Decimal | None:
    if baseline is None or baseline == 0:
        return None
    return ((actual / baseline) - 1) * Decimal("100")


def _explorer_query(promo: Promo) -> str:
    groups = [row.product_group.granit_id for row in promo.promo_products.all() if row.product_group_id]
    products = [row.product.granit_id for row in promo.promo_products.all() if row.product_id]
    params = {
        "date_from": promo.start_date.isoformat(),
        "date_to": promo.end_date.isoformat(),
        "group_by": "day",
    }
    if len(products) == 1 and not groups:
        params["product"] = products[0]
        params["group_by"] = "receipt"
    elif len(groups) == 1 and not products:
        params["group"] = groups[0]
    return urlencode(params)


def promo_list(request):
    today = date.today()
    tab = request.GET.get("tab") or "active"
    if tab not in ("active", "passed"):
        tab = "active"
    qs = Promo.objects.prefetch_related("promo_products", "analyses")
    if tab == "active":
        promos = qs.filter(end_date__gte=today)
    else:
        promos = qs.filter(end_date__lt=today)

    rows = []
    for promo in promos:
        sku_count = len(target_product_ids(promo))
        rows.append(
            {
                "promo": promo,
                "sku_count": sku_count,
                "estimated_earnings": promo_estimated_earnings_total(promo),
            }
        )
    return render(
        request,
        "promos/list.html",
        {
            "tab": tab,
            "rows": rows,
            "active_count": Promo.objects.filter(end_date__gte=today).count(),
            "passed_count": Promo.objects.filter(end_date__lt=today).count(),
            "catalog": catalog_status(),
        },
    )


def promo_example_xlsx(request):
    ensure_example_files()
    if not DOCS_PROMOS_XLSX.is_file():
        raise Http404(_("Example promo file is not available."))
    return FileResponse(
        DOCS_PROMOS_XLSX.open("rb"),
        as_attachment=True,
        filename="promos_example.xlsx",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def _form_context(form: PromoForm, **extra) -> dict:
    return {
        "form": form,
        "selected_items": form.selected_product_items(),
        "selected_groups": form.selected_groups(),
        "catalog": catalog_status(),
        **extra,
    }


def promo_create(request):
    example_path = ensure_example_files()
    if request.method == "POST":
        form = PromoForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                created = _save_promos(form)
            except ValueError as exc:
                messages.error(request, str(exc))
            else:
                if len(created) == 1:
                    messages.success(request, _("Promo saved and calculated."))
                    return redirect("promo_detail", pk=created[0].pk)
                messages.success(
                    request,
                    _("Saved %(count)s promos from the table.") % {"count": len(created)},
                )
                return redirect("promo_list")
    else:
        form = PromoForm()
        form.date_defaults()
    return render(
        request,
        "promos/create.html",
        _form_context(form, example_exists=bool(example_path and example_path.is_file())),
    )


def promo_edit(request, pk: int):
    promo = get_object_or_404(Promo.objects.prefetch_related("promo_products"), pk=pk)
    if request.method == "POST":
        form = PromoForm(request.POST, promo=promo)
        if form.is_valid():
            _update_promo(promo, form.cleaned_data)
            messages.success(request, _("Promo saved and calculated."))
            return redirect("promo_detail", pk=promo.pk)
    else:
        form = PromoForm(promo=promo)
    return render(request, "promos/create.html", _form_context(form, promo=promo))


def _apply_fields(promo: Promo, cleaned: dict) -> None:
    promo.name = cleaned["name"]
    promo.start_date = cleaned["start_date"]
    promo.end_date = cleaned["end_date"]
    promo.pre_period_days = cleaned["pre_period_days"]
    promo.notes = cleaned.get("notes") or ""
    promo.promo_type = cleaned.get("promo_type") or ""
    promo.format = cleaned.get("format") or ""
    promo.channels = cleaned.get("channels") or ""


def _replace_targets(promo: Promo, cleaned: dict) -> None:
    """Rebuild PromoProduct rows, keeping manual_sale_price of products that stay."""
    manual = dict(
        promo.promo_products.filter(product__isnull=False, manual_sale_price__isnull=False)
        .values_list("product_id", "manual_sale_price")
    )
    targets = []
    seen_products, seen_groups = set(), set()
    for group in cleaned.get("group_ids") or []:
        if group.pk not in seen_groups:
            seen_groups.add(group.pk)
            targets.append(PromoProduct(promo=promo, product_group=group))
    for product in cleaned.get("product_ids") or []:
        if product.pk not in seen_products:
            seen_products.add(product.pk)
            targets.append(
                PromoProduct(promo=promo, product=product, manual_sale_price=manual.get(product.pk))
            )
    with transaction.atomic():
        promo.promo_products.all().delete()
        PromoProduct.objects.bulk_create(targets)


def _update_promo(promo: Promo, cleaned: dict) -> None:
    _apply_fields(promo, cleaned)
    promo.save()
    _replace_targets(promo, cleaned)
    analyze_promo(promo)


def _save_promos(form: PromoForm) -> list[Promo]:
    cleaned = form.cleaned_data
    source = None
    if cleaned.get("excel_file"):
        source = cleaned["excel_file"]
    elif cleaned.get("use_example_file") and LOCAL_PROMOS_XLSX.is_file():
        source = LOCAL_PROMOS_XLSX
    if source is not None:
        rows = parse_promo_xlsx(source)
        if not rows:
            raise ValueError(_("The promo table has no group_id or product_id rows."))
        return import_promo_rows(
            rows,
            default_name=cleaned.get("name") or "",
            default_start=cleaned.get("start_date"),
            default_end=cleaned.get("end_date"),
            default_days=cleaned.get("pre_period_days") or 14,
            default_notes=cleaned.get("notes") or "",
        )
    promo = Promo()
    _update_promo(promo, cleaned)
    return [promo]


def promo_detail(request, pk: int):
    promo = get_object_or_404(
        Promo.objects.prefetch_related(
            "promo_products__product", "promo_products__product_group", "analyses"
        ),
        pk=pk,
    )
    days = list(promo.analyses.all())
    n_days = len(days)
    actual_sum = sum((row.actual_sales for row in days), Decimal("0"))
    pre = days[0].baseline_pre_period if days else None
    yoy = days[0].baseline_yoy if days else None
    baseline_sum = (pre * n_days) if pre is not None else None
    yoy_sum = (yoy * n_days) if yoy is not None else None
    forecast_sum = sum((row.forecast_value or Decimal("0") for row in days), Decimal("0")) if days else None
    has_forecast = any(row.forecast_value is not None for row in days)
    targets = []
    for row in promo.promo_products.all():
        if row.product_id:
            targets.append(row.product.name)
        elif row.product_group_id:
            targets.append(row.product_group.name)
    price_rows = build_promo_price_rows(promo)
    earnings_total = sum(
        (r.estimated_earnings for r in price_rows if r.estimated_earnings is not None),
        Decimal("0"),
    )
    has_earnings = any(r.estimated_earnings is not None for r in price_rows)
    return render(
        request,
        "promos/detail.html",
        {
            "promo": promo,
            "days": days,
            "targets": targets,
            "price_rows": price_rows,
            "earnings_total": earnings_total if has_earnings else None,
            "actual_sum": actual_sum,
            "baseline_sum": baseline_sum,
            "yoy_sum": yoy_sum,
            "forecast_sum": forecast_sum if has_forecast else None,
            "lift_pre": _lift(actual_sum, baseline_sum),
            "lift_yoy": _lift(actual_sum, yoy_sum),
            "yoy_missing": n_days > 0 and yoy is None,
            "explorer_query": _explorer_query(promo),
            "today": date.today(),
        },
    )


def promo_charts(request, pk: int):
    from promos.charts import build_promo_charts

    promo = get_object_or_404(Promo, pk=pk)
    labels = {
        "actual": _("Actual"),
        "baseline": _("Pre-period baseline"),
        "yoy": _("Last year"),
        "forecast": _("Forecast"),
    }
    return render(
        request,
        "promos/charts.html",
        {"promo": promo, "charts": build_promo_charts(promo, labels)},
    )


@require_POST
def promo_reanalyze(request, pk: int):
    promo = get_object_or_404(Promo, pk=pk)
    analyze_promo(promo)
    messages.success(request, _("This promo was recalculated."))
    return redirect("promo_detail", pk=promo.pk)
