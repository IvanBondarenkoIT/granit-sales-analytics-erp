from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from django.db.models import Sum

from campaigns.analysis import (
    LOCAL_SMS_XLSX,
    analyze_rows,
    import_campaign_from_path,
    prefetch_card_clients,
)
from campaigns.excel import CampaignRow, parse_campaign_xlsx
from campaigns.forms import CampaignUploadForm
from campaigns.models import Campaign, CampaignClient
from campaigns.tg_csv import parse_tg_users_csv
from core.models import Product, ProductGroup
from sales.models import SaleFact

CLIENT_LIMIT = 500


def _int_param(request, name: str) -> int | None:
    raw = (request.GET.get(name) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _apply_catalog_filter(qs, group_id: int | None, product_id: int | None):
    if product_id is not None:
        qs = qs.filter(product__granit_id=product_id)
    elif group_id is not None:
        qs = qs.filter(product__group__granit_id=group_id)
    return qs


def _campaign_client_ids(campaign: Campaign) -> list[int]:
    return list(
        campaign.campaign_clients.exclude(client_id=None).values_list("client_id", flat=True)
    )


def _catalog_filter_context(request, campaign: Campaign, client_ids: list[int]) -> dict:
    group_id = _int_param(request, "group")
    product_id = _int_param(request, "product")
    if product_id is not None and group_id is not None:
        if not Product.objects.filter(granit_id=product_id, group__granit_id=group_id).exists():
            product_id = None
    sales = _campaign_sales_qs(campaign).filter(client_id__in=client_ids)
    group_ids = list(sales.exclude(product__group_id=None).values_list("product__group_id", flat=True).distinct())
    groups = ProductGroup.objects.filter(id__in=group_ids).order_by("name")
    products_qs = Product.objects.filter(
        id__in=sales.values_list("product_id", flat=True).distinct()
    ).select_related("group").order_by("name")
    if group_id is not None:
        products_qs = products_qs.filter(group__granit_id=group_id)
    query = ""
    if group_id is not None:
        query += f"&group={group_id}"
    if product_id is not None:
        query += f"&product={product_id}"
    return {
        "filter_group_id": group_id,
        "filter_product_id": product_id,
        "filter_groups": groups,
        "filter_products": products_qs[:400],
        "filter_query": query,
        "filter_active": group_id is not None or product_id is not None,
    }


def campaign_list(request):
    campaigns = Campaign.objects.all()
    return render(request, "campaigns/list.html", {"campaigns": campaigns})


def campaign_create(request):
    if request.method == "POST":
        form = CampaignUploadForm(request.POST, request.FILES)
        if form.is_valid():
            sent = form.cleaned_data["sms_sent_on"]
            date_to = form.cleaned_data["date_to"]
            notes = form.cleaned_data["notes"]
            try:
                if form.cleaned_data["use_local_file"] and LOCAL_SMS_XLSX.is_file():
                    campaign = import_campaign_from_path(
                        LOCAL_SMS_XLSX,
                        name=form.cleaned_data["name"],
                        date_from=sent,
                        date_to=date_to,
                        sms_sent_on=sent,
                        notes=notes,
                    )
                else:
                    channel = form.cleaned_data["channel"]
                    upload = form.cleaned_data["excel_file"]
                    if channel == Campaign.CHANNEL_TELEGRAM:
                        rows = parse_tg_users_csv(upload)
                        if not rows:
                            raise ValueError(_("CSV has no card rows"))
                        prefetch_card_clients(rows)
                        upload.seek(0)
                    else:
                        rows = parse_campaign_xlsx(upload)
                    campaign = Campaign.objects.create(
                        name=form.cleaned_data["name"],
                        channel=channel,
                        sms_sent_on=sent,
                        notes=notes,
                    )
                    if upload:
                        campaign.uploaded_file.save(upload.name, upload, save=True)
                    campaign = analyze_rows(campaign, rows, sent, date_to)
            except Exception as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, _("New campaign saved separately from previous blasts."))
                return redirect("campaign_detail", pk=campaign.pk)
    else:
        form = CampaignUploadForm(
            initial={
                "name": _("SMS %(date)s") % {"date": date.today().isoformat()},
                "sms_sent_on": date.today(),
            }
        )
    return render(
        request,
        "campaigns/create.html",
        {"form": form, "local_file_exists": LOCAL_SMS_XLSX.is_file()},
    )


def campaign_detail(request, pk: int):
    campaign = get_object_or_404(Campaign, pk=pk)
    status = request.GET.get("status", "all")
    client_ids = _campaign_client_ids(campaign)
    filters = _catalog_filter_context(request, campaign, client_ids)
    group_id = filters["filter_group_id"]
    product_id = filters["filter_product_id"]
    filtered = group_id is not None or product_id is not None

    bought_map = {}
    if filtered:
        bought_map = {
            row["client_id"]: {"amount": row["amount"] or 0}
            for row in _apply_catalog_filter(
                _campaign_sales_qs(campaign).filter(client_id__in=client_ids),
                group_id,
                product_id,
            )
            .values("client_id")
            .annotate(amount=Sum("amount"))
        }

    rows = []
    bought_count = 0
    for item in campaign.campaign_clients.select_related("client"):
        if filtered:
            hit = item.client_id in bought_map
            amount = bought_map[item.client_id]["amount"] if hit else 0
        else:
            hit = item.had_sales
            amount = item.sales_amount
        if hit:
            bought_count += 1
        if status == "bought" and not hit:
            continue
        if status == "not_bought" and hit:
            continue
        item.view_bought = hit
        item.view_amount = amount
        rows.append(item)
    rows.sort(
        key=lambda r: (-bool(r.view_bought), -float(r.view_amount or 0), r.granit_client_id or 0, r.card_number)
    )
    row_count = len(rows)
    clients = rows[:CLIENT_LIMIT]
    matching_amount = sum((row.view_amount or Decimal("0") for row in rows), Decimal("0"))
    shown_amount = sum((row.view_amount or Decimal("0") for row in clients), Decimal("0"))
    total = campaign.total_clients
    rate = round(100.0 * bought_count / total, 1) if total else 0.0
    return render(
        request,
        "campaigns/detail.html",
        {
            "campaign": campaign,
            "clients": clients,
            "row_count": row_count,
            "row_limit": CLIENT_LIMIT,
            "truncated": row_count > CLIENT_LIMIT,
            "shown_amount": shown_amount,
            "matching_amount": matching_amount,
            "status": status,
            "rate": rate,
            "bought_count": bought_count,
            "not_bought": total - bought_count,
            "unmatched": CampaignClient.objects.filter(campaign=campaign, client__isnull=True).count(),
            "today": date.today(),
            "show_cards": campaign.channel == Campaign.CHANNEL_TELEGRAM,
            "filter_action": "campaign_detail",
            **filters,
        },
    )


@require_POST
def campaign_reanalyze(request, pk: int):
    campaign = get_object_or_404(Campaign, pk=pk)
    raw_to = request.POST.get("date_to")
    try:
        date_to = date.fromisoformat(raw_to) if raw_to else date.today()
    except ValueError:
        messages.error(request, _("Invalid end date."))
        return redirect("campaign_detail", pk=campaign.pk)
    sent = campaign.sms_sent_on or campaign.analysis_period_start
    if not sent or date_to <= sent:
        messages.error(request, _("Analysis end must be after the send date."))
        return redirect("campaign_detail", pk=campaign.pk)
    typed = [
        CampaignRow(
            granit_client_id=item.granit_client_id,
            phone=item.phone,
            card_number=item.card_number,
        )
        for item in campaign.campaign_clients.all()
    ]
    prefetch_card_clients(typed)
    analyze_rows(campaign, typed, sent, date_to)
    messages.success(request, _("This campaign was recalculated. Other blasts were not changed."))
    return redirect("campaign_detail", pk=campaign.pk)


def _campaign_sales_qs(campaign: Campaign):
    date_from = campaign.analysis_period_start
    date_to = campaign.analysis_period_end
    qs = SaleFact.objects.select_related("product", "product__group", "store", "client")
    if date_from:
        qs = qs.filter(sale_date__gte=date_from)
    if date_to:
        qs = qs.filter(sale_date__lt=date_to)
    return qs


def campaign_purchases(request, pk: int):
    campaign = get_object_or_404(Campaign, pk=pk)
    client_ids = _campaign_client_ids(campaign)
    filters = _catalog_filter_context(request, campaign, client_ids)
    products = (
        _apply_catalog_filter(
            _campaign_sales_qs(campaign).filter(client_id__in=client_ids),
            filters["filter_group_id"],
            filters["filter_product_id"],
        )
        .values("product__name", "product__granit_id", "product__group__name")
        .annotate(qty=Sum("quantity"), amount=Sum("amount"))
        .order_by("-amount")[:200]
    )
    return render(
        request,
        "campaigns/purchases.html",
        {
            "campaign": campaign,
            "products": products,
            "filter_action": "campaign_purchases",
            **filters,
        },
    )


def campaign_client_purchases(request, pk: int, row_pk: int):
    campaign = get_object_or_404(Campaign, pk=pk)
    row = get_object_or_404(CampaignClient, pk=row_pk, campaign=campaign)
    client_ids = [row.client_id] if row.client_id else []
    filters = _catalog_filter_context(request, campaign, _campaign_client_ids(campaign))
    lines = []
    if row.client_id:
        lines = list(
            _apply_catalog_filter(
                _campaign_sales_qs(campaign).filter(client_id=row.client_id),
                filters["filter_group_id"],
                filters["filter_product_id"],
            ).order_by("sale_date", "granit_sale_id", "granit_line_id")
        )
    orders = []
    current = None
    for line in lines:
        if current is None or current["sale_id"] != line.granit_sale_id:
            current = {
                "sale_id": line.granit_sale_id,
                "sale_date": line.sale_date,
                "store": line.store.name,
                "amount": line.amount,
                "lines": [line],
            }
            orders.append(current)
        else:
            current["lines"].append(line)
            current["amount"] += line.amount
    return render(
        request,
        "campaigns/client_purchases.html",
        {
            "campaign": campaign,
            "row": row,
            "orders": orders,
            "filter_action": "campaign_client_purchases",
            "filter_row_pk": row.pk,
            **filters,
        },
    )
