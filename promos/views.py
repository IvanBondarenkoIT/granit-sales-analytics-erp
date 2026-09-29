from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core.models import Product
from promos.analysis import analyze_promo, import_promo_rows
from promos.excel import DOCS_PROMOS_XLSX, LOCAL_PROMOS_XLSX, ensure_example_files, parse_promo_xlsx
from promos.forms import PromoForm
from promos.models import Promo, PromoProduct


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
    promos = Promo.objects.prefetch_related("promo_products", "analyses")
    return render(request, "promos/list.html", {"promos": promos})


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


def promo_product_options(request):
    group_ids = request.GET.getlist("groups")
    products = Product.objects.none()
    if group_ids:
        products = Product.objects.filter(group_id__in=group_ids).order_by("name")[:400]
    return render(request, "promos/_product_options.html", {"products": products})


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
        {
            "form": form,
            "example_exists": bool(example_path and example_path.is_file()),
        },
    )


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
    promo = Promo.objects.create(
        name=cleaned["name"],
        start_date=cleaned["start_date"],
        end_date=cleaned["end_date"],
        pre_period_days=cleaned["pre_period_days"],
        notes=cleaned["notes"],
    )
    targets = []
    for group in cleaned["groups"]:
        targets.append(PromoProduct(promo=promo, product_group=group))
    for product in cleaned["products"]:
        targets.append(PromoProduct(promo=promo, product=product))
    PromoProduct.objects.bulk_create(targets)
    analyze_promo(promo)
    return [promo]


def promo_detail(request, pk: int):
    promo = get_object_or_404(
        Promo.objects.prefetch_related("promo_products__product", "promo_products__product_group", "analyses"),
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
    return render(
        request,
        "promos/detail.html",
        {
            "promo": promo,
            "days": days,
            "targets": targets,
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


@require_POST
def promo_reanalyze(request, pk: int):
    promo = get_object_or_404(Promo, pk=pk)
    analyze_promo(promo)
    messages.success(request, _("This promo was recalculated."))
    return redirect("promo_detail", pk=promo.pk)
