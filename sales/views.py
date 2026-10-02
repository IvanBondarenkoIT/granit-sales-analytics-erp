from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.conf import settings
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import render
from django.utils.translation import gettext as _

from core.models import Product, ProductGroup, ProductParameterValue, Store
from sales.models import SCOPE_ALL, SCOPE_RETAIL, SCOPES, SOURCE_INVOICE, SOURCE_RECEIPT, SaleFact

ROW_LIMIT = 300
GROUP_BY_OPTIONS = ("product", "group", "param", "store", "client", "day", "receipt")
SORT_OPTIONS = ("amount", "quantity", "name")

GROUP_BY_VALUES = {
    "product": ("product__granit_id", "product__name", "product__group__name"),
    "group": ("product__group__granit_id", "product__group__name"),
    "param": ("product__parameter_value__granit_id", "product__parameter_value__label"),
    "store": ("store__granit_id", "store__name"),
    "client": ("client__granit_id", "client__name"),
    "day": ("sale_date",),
    "receipt": ("source", "granit_sale_id", "sale_date", "store__name", "client__granit_id", "client__name"),
}


def _int_param(request, name: str) -> int | None:
    raw = (request.GET.get(name) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _parse_date(raw: str | None, fallback: date) -> date:
    if not raw:
        return fallback
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return fallback


def _default_range() -> tuple[date, date]:
    latest = SaleFact.objects.order_by("-sale_date").values_list("sale_date", flat=True).first()
    end = latest or date.today()
    return end - timedelta(days=29), end


def _choice(raw: str | None, allowed: tuple[str, ...], fallback: str) -> str:
    if raw in allowed:
        return raw
    return fallback


def _scope(request) -> str:
    return _choice(request.GET.get("scope"), SCOPES, SCOPE_RETAIL)


def _scope_choices() -> list[tuple[str, str]]:
    return [(SCOPE_RETAIL, _("Retail")), (SCOPE_ALL, _("All warehouses"))]


def _stores_with_sales(scope: str):
    sold = SaleFact.objects.for_scope(scope).values("store_id").distinct()
    return Store.objects.filter(id__in=sold).order_by("name")


def _scope_context(scope: str) -> dict:
    return {"scope": scope, "scope_choices": _scope_choices(), "scope_all": scope == SCOPE_ALL}


def _encode_params(params: dict) -> str:
    items = []
    for key, value in params.items():
        if value in (None, ""):
            continue
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        items.append((key, str(value)))
    return urlencode(items)


def _apply_filters(qs, *, date_from, date_to, store_id, group_id, product_id, param_id, client_id, query):
    qs = qs.filter(sale_date__gte=date_from, sale_date__lte=date_to)
    if store_id is not None:
        qs = qs.filter(store__granit_id=store_id)
    if product_id is not None:
        qs = qs.filter(product__granit_id=product_id)
    elif group_id is not None:
        qs = qs.filter(product__group__granit_id=group_id)
    if param_id is not None:
        qs = qs.filter(product__parameter_value__granit_id=param_id)
    if client_id is not None:
        qs = qs.filter(client__granit_id=client_id)
    if query:
        qs = qs.filter(product__name__icontains=query)
    return qs


def _label_rows(group_by: str, rows: list[dict], base_params: dict) -> list[dict]:
    labeled = []
    for row in rows:
        sale_id = None
        is_invoice = False
        receipts_params = dict(base_params)
        receipts_params["group_by"] = "receipt"
        if group_by == "product":
            name = row.get("product__name") or "—"
            secondary = row.get("product__group__name") or "—"
            if row.get("product__granit_id") is not None:
                receipts_params["product"] = row["product__granit_id"]
        elif group_by == "group":
            name = row.get("product__group__name") or "—"
            secondary = ""
            if row.get("product__group__granit_id") is not None:
                receipts_params["group"] = row["product__group__granit_id"]
                receipts_params["product"] = None
        elif group_by == "param":
            name = row.get("product__parameter_value__label") or "—"
            secondary = ""
            if row.get("product__parameter_value__granit_id") is not None:
                receipts_params["param"] = row["product__parameter_value__granit_id"]
        elif group_by == "store":
            name = row.get("store__name") or "—"
            secondary = ""
            if row.get("store__granit_id") is not None:
                receipts_params["store"] = row["store__granit_id"]
        elif group_by == "client":
            name = row.get("client__name") or "—"
            secondary = row.get("client__granit_id") or "—"
            if row.get("client__granit_id") is not None:
                receipts_params["client"] = row["client__granit_id"]
            else:
                receipts_params = None
        elif group_by == "receipt":
            sale_id = row.get("granit_sale_id")
            name = sale_id
            secondary = row.get("sale_date")
            receipts_params = None
            is_invoice = row.get("source") == SOURCE_INVOICE
        else:
            name = row.get("sale_date")
            secondary = ""
            if row.get("sale_date"):
                receipts_params["date_from"] = row["sale_date"]
                receipts_params["date_to"] = row["sale_date"]
        labeled.append(
            {
                "name": name,
                "secondary": secondary,
                "store_name": row.get("store__name") or "—",
                "client_name": row.get("client__name") or "—",
                "client_granit_id": row.get("client__granit_id"),
                "sale_id": sale_id,
                "is_invoice": is_invoice,
                "receipts_query": _encode_params(receipts_params) if receipts_params else "",
                "qty": row.get("qty") or Decimal("0"),
                "amount": row.get("amount") or Decimal("0"),
            }
        )
    return labeled


def _explorer_context(request) -> dict:
    default_from, default_to = _default_range()
    date_from = _parse_date(request.GET.get("date_from"), default_from)
    date_to = _parse_date(request.GET.get("date_to"), default_to)
    if date_to < date_from:
        date_from, date_to = date_to, date_from

    store_id = _int_param(request, "store")
    group_id = _int_param(request, "group")
    product_id = _int_param(request, "product")
    param_id = _int_param(request, "param")
    client_id = _int_param(request, "client")
    query = (request.GET.get("q") or "").strip()
    group_by = _choice(request.GET.get("group_by"), GROUP_BY_OPTIONS, "product")
    sort = _choice(request.GET.get("sort"), SORT_OPTIONS, "amount")
    scope = _scope(request)

    if product_id is not None and group_id is not None:
        if not Product.objects.filter(granit_id=product_id, group__granit_id=group_id).exists():
            product_id = None

    qs = _apply_filters(
        SaleFact.objects.for_scope(scope),
        date_from=date_from,
        date_to=date_to,
        store_id=store_id,
        group_id=group_id,
        product_id=product_id,
        param_id=param_id,
        client_id=client_id,
        query=query,
    )

    values = GROUP_BY_VALUES[group_by]
    aggregated = qs.values(*values).annotate(qty=Sum("quantity"), amount=Sum("amount"))
    if sort == "quantity":
        aggregated = aggregated.order_by("-qty", "-amount")
    elif sort == "name":
        name_field = "sale_date" if group_by in {"day", "receipt"} else (values[1] if len(values) > 1 else values[0])
        aggregated = aggregated.order_by(name_field)
    else:
        aggregated = aggregated.order_by("-amount", "-qty")

    base_params = {
        "date_from": date_from,
        "date_to": date_to,
        "store": store_id,
        "group": group_id,
        "product": product_id,
        "param": param_id,
        "client": client_id,
        "q": query,
        "group_by": group_by,
        "sort": sort,
        "scope": scope if scope == SCOPE_ALL else None,
    }
    total_rows = aggregated.count()
    rows = _label_rows(group_by, list(aggregated[:ROW_LIMIT]), base_params)
    totals = qs.aggregate(qty=Sum("quantity"), amount=Sum("amount"))

    products_qs = Product.objects.order_by("name")
    if group_id is not None:
        products_qs = products_qs.filter(group__granit_id=group_id)
    else:
        products_qs = products_qs.filter(id__in=qs.values("product_id"))

    param_values = ProductParameterValue.objects.filter(
        parameter__granit_id=settings.ETL_PRODUCT_PARAM_ID
    ).order_by("label")

    return {
        **_scope_context(scope),
        "date_from": date_from,
        "date_to": date_to,
        "store_id": store_id,
        "group_id": group_id,
        "product_id": product_id,
        "param_id": param_id,
        "client_id": client_id or "",
        "q": query,
        "group_by": group_by,
        "sort": sort,
        "explorer_query": _encode_params(base_params),
        "stores": _stores_with_sales(scope),
        "groups": ProductGroup.objects.order_by("name"),
        "products": products_qs[:400],
        "param_values": param_values,
        "rows": rows,
        "row_count": total_rows,
        "row_limit": ROW_LIMIT,
        "truncated": total_rows > ROW_LIMIT,
        "total_qty": totals["qty"] or Decimal("0"),
        "total_amount": totals["amount"] or Decimal("0"),
        "name_heading": {
            "product": _("Product"),
            "group": _("Product group"),
            "param": _("Production"),
            "store": _("Store"),
            "client": _("Client"),
            "day": _("Day"),
            "receipt": _("Receipt"),
        }[group_by],
        "show_secondary": group_by in {"product", "client", "receipt"},
        "secondary_heading": {
            "product": _("Product group"),
            "client": _("Client ID"),
            "receipt": _("Day"),
        }.get(group_by, ""),
        "group_by_choices": [
            ("product", _("Product")),
            ("group", _("Product group")),
            ("param", _("Production")),
            ("store", _("Store")),
            ("client", _("Client")),
            ("day", _("Day")),
            ("receipt", _("Receipt")),
        ],
        "sort_choices": [
            ("amount", _("Amount")),
            ("quantity", _("Qty")),
            ("name", _("Name")),
        ],
    }


def sales_explorer(request):
    context = _explorer_context(request)
    template = "sales/_explorer.html" if request.htmx else "sales/explorer.html"
    return render(request, template, context)


def sales_receipt(request, sale_id: int):
    source = _choice(request.GET.get("source"), (SOURCE_RECEIPT, SOURCE_INVOICE), SOURCE_RECEIPT)
    lines = list(
        SaleFact.objects.filter(granit_sale_id=sale_id, source=source)
        .select_related("product", "product__group", "store", "client")
        .order_by("granit_line_id")
    )
    if not lines:
        raise Http404(_("Receipt not found."))
    first = lines[0]
    highlight = _int_param(request, "product")
    return render(
        request,
        "sales/receipt.html",
        {
            "sale_id": sale_id,
            "is_invoice": source == SOURCE_INVOICE,
            "sale_date": first.sale_date,
            "store": first.store,
            "client": first.client,
            "lines": lines,
            "total_qty": sum((line.quantity for line in lines), Decimal("0")),
            "total_amount": sum((line.amount for line in lines), Decimal("0")),
            "highlight_product_id": highlight,
            "back_query": request.GET.urlencode(),
        },
    )


def _matrix_period(request) -> tuple[date, date]:
    default_from, default_to = _default_range()
    date_from = _parse_date(request.GET.get("date_from"), default_from)
    date_to = _parse_date(request.GET.get("date_to"), default_to)
    if date_to < date_from:
        date_from, date_to = date_to, date_from
    return date_from, date_to


def sales_matrix(request):
    from sales.matrix import build_matrix

    date_from, date_to = _matrix_period(request)
    scope = _scope(request)
    matrix = build_matrix(date_from, date_to, scope)
    return render(
        request,
        "sales/matrix.html",
        {
            **_scope_context(scope),
            "matrix": matrix,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


def sales_matrix_xlsx(request):
    from django.http import HttpResponse

    from sales.excel_matrix import matrix_to_xlsx
    from sales.matrix import build_matrix

    date_from, date_to = _matrix_period(request)
    scope = _scope(request)
    matrix = build_matrix(date_from, date_to, scope)
    payload = matrix_to_xlsx(matrix)
    suffix = "_all" if scope == SCOPE_ALL else ""
    filename = f"supergroups{suffix}_{date_from.isoformat()}_{date_to.isoformat()}.xlsx"
    response = HttpResponse(
        payload,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def sales_matrix_edit(request):
    from django.contrib import messages
    from django.db import transaction
    from django.shortcuts import redirect

    from sales.models import SuperGroup

    def _ordered_groups():
        return list(SuperGroup.objects.filter(is_catchall=False).order_by("sort_order", "title", "pk"))

    def _renumber(groups):
        for idx, sg in enumerate(groups):
            if sg.sort_order != idx:
                sg.sort_order = idx
                sg.save(update_fields=["sort_order", "updated_at"])

    from sales.matrix import period_query

    date_from, date_to = _matrix_period(request)
    back_query = period_query(date_from, date_to, _scope(request))
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            key = (request.POST.get("key") or "").strip().lower().replace(" ", "_")
            title = (request.POST.get("title") or "").strip()
            color = (request.POST.get("color") or "CCCCCC").lstrip("#")[:6]
            if not key or not title:
                messages.error(request, _("Key and title are required."))
            elif SuperGroup.objects.filter(key=key).exists():
                messages.error(request, _("A super-group with this key already exists."))
            else:
                order = SuperGroup.objects.filter(is_catchall=False).count()
                SuperGroup.objects.create(key=key, title=title, color=color or "CCCCCC", sort_order=order)
                messages.success(request, _("Super-group created."))
        elif action == "update":
            sg = SuperGroup.objects.filter(pk=request.POST.get("sg_id"), is_catchall=False).first()
            if sg:
                sg.title = (request.POST.get("title") or sg.title).strip() or sg.title
                sg.color = (request.POST.get("color") or sg.color).lstrip("#")[:6]
                sg.save()
                messages.success(request, _("Super-group updated."))
        elif action == "delete":
            sg = SuperGroup.objects.filter(pk=request.POST.get("sg_id"), is_catchall=False).first()
            if sg:
                sg.delete()
                _renumber(_ordered_groups())
                messages.success(request, _("Super-group deleted; its groups are outside again."))
        elif action in {"move_up", "move_down"}:
            sg = SuperGroup.objects.filter(pk=request.POST.get("sg_id"), is_catchall=False).first()
            if sg:
                with transaction.atomic():
                    groups = _ordered_groups()
                    ids = [g.pk for g in groups]
                    try:
                        idx = ids.index(sg.pk)
                    except ValueError:
                        idx = -1
                    swap_with = idx - 1 if action == "move_up" else idx + 1
                    if idx >= 0 and 0 <= swap_with < len(groups):
                        groups[idx], groups[swap_with] = groups[swap_with], groups[idx]
                        _renumber(groups)
                        messages.success(request, _("Order updated."))
        return redirect(f"{request.path}?{back_query}")

    groups = _ordered_groups()
    catchall = SuperGroup.objects.filter(is_catchall=True).first()
    return render(
        request,
        "sales/matrix_edit.html",
        {
            "super_groups": groups,
            "catchall": catchall,
            "date_from": date_from,
            "date_to": date_to,
            "period_query": back_query,
        },
    )


def sales_matrix_sg(request, pk: int):
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect

    from sales.matrix import group_sales_for_super_group, period_query, unassigned_groups
    from sales.models import SuperGroup, SuperGroupMember

    sg = get_object_or_404(SuperGroup, pk=pk)
    date_from, date_to = _matrix_period(request)
    store_id = _int_param(request, "store")
    scope = _scope(request)

    if request.method == "POST" and not sg.is_catchall:
        action = request.POST.get("action")
        if action == "remove":
            SuperGroupMember.objects.filter(
                super_group=sg, product_group__granit_id=request.POST.get("group_id")
            ).delete()
            messages.success(request, _("Group removed from super-group."))
        elif action == "add":
            group = ProductGroup.objects.filter(granit_id=request.POST.get("group_id")).first()
            if group:
                SuperGroupMember.objects.update_or_create(
                    product_group=group,
                    defaults={"super_group": sg},
                )
                messages.success(request, _("Group added to super-group."))
        q = period_query(date_from, date_to, scope, store=store_id)
        return redirect(f"{request.path}?{q}")

    rows = group_sales_for_super_group(sg, date_from, date_to, store_id, scope)
    available = []
    if not sg.is_catchall:
        available = list(
            unassigned_groups(request.GET.get("q") or "", date_from=date_from, date_to=date_to, scope=scope)
        )
    return render(
        request,
        "sales/matrix_sg.html",
        {
            **_scope_context(scope),
            "matrix_query": period_query(date_from, date_to, scope),
            "sg": sg,
            "rows": rows,
            "available": available,
            "date_from": date_from,
            "date_to": date_to,
            "store_id": store_id,
            "stores": _stores_with_sales(scope),
            "period_query": period_query(date_from, date_to, scope, store=store_id),
            "total_qty": sum((r["qty"] for r in rows), Decimal("0")),
            "total_amount": sum((r["amount"] for r in rows), Decimal("0")),
        },
    )


def sales_matrix_group(request, granit_id: int):
    from django.contrib import messages
    from django.shortcuts import get_object_or_404, redirect

    from sales.matrix import period_query, product_sales_for_group
    from sales.models import SuperGroup, SuperGroupMember

    group = get_object_or_404(ProductGroup, granit_id=granit_id)
    date_from, date_to = _matrix_period(request)
    store_id = _int_param(request, "store")
    scope = _scope(request)

    if request.method == "POST" and request.POST.get("action") == "set_owner":
        sg_id = (request.POST.get("sg_id") or "").strip()
        if not sg_id or sg_id == "outside":
            SuperGroupMember.objects.filter(product_group=group).delete()
            messages.success(request, _("Group moved to outside super-groups."))
        else:
            sg = SuperGroup.objects.filter(pk=sg_id, is_catchall=False).first()
            if sg:
                SuperGroupMember.objects.update_or_create(
                    product_group=group,
                    defaults={"super_group": sg},
                )
                messages.success(request, _("Super-group owner updated."))
            else:
                messages.error(request, _("Super-group not found."))
        return redirect(f"{request.path}?{period_query(date_from, date_to, scope, store=store_id)}")

    rows = product_sales_for_group(granit_id, date_from, date_to, store_id, scope)
    member = SuperGroupMember.objects.filter(product_group=group).select_related("super_group").first()
    current_sg = member.super_group if member else None
    explorer_params = {
        "date_from": date_from,
        "date_to": date_to,
        "group": granit_id,
        "group_by": "product",
        "scope": scope if scope == SCOPE_ALL else None,
    }
    if store_id is not None:
        explorer_params["store"] = store_id
    return render(
        request,
        "sales/matrix_group.html",
        {
            **_scope_context(scope),
            "matrix_query": period_query(date_from, date_to, scope),
            "group": group,
            "rows": rows,
            "date_from": date_from,
            "date_to": date_to,
            "store_id": store_id,
            "period_query": period_query(date_from, date_to, scope, store=store_id),
            "explorer_query": _encode_params(explorer_params),
            "total_qty": sum((r["qty"] for r in rows), Decimal("0")),
            "total_amount": sum((r["amount"] for r in rows), Decimal("0")),
            "current_sg": current_sg,
            "super_groups": list(
                SuperGroup.objects.filter(is_catchall=False).order_by("sort_order", "title")
            ),
        },
    )
