from datetime import date

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from django.db.models import Sum

from campaigns.analysis import LOCAL_SMS_XLSX, analyze_rows, import_campaign_from_path
from campaigns.excel import CampaignRow, parse_campaign_xlsx
from campaigns.forms import CampaignUploadForm
from campaigns.models import Campaign, CampaignClient
from sales.models import SaleFact


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
                    upload = form.cleaned_data["excel_file"]
                    rows = parse_campaign_xlsx(upload)
                    campaign = Campaign.objects.create(
                        name=form.cleaned_data["name"],
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
    qs = campaign.campaign_clients.select_related("client")
    if status == "bought":
        qs = qs.filter(had_sales=True)
    elif status == "not_bought":
        qs = qs.filter(had_sales=False)
    clients = qs.order_by("-had_sales", "-sales_amount", "granit_client_id")[:500]
    rate = 0.0
    if campaign.total_clients:
        rate = round(100.0 * campaign.clients_with_sales / campaign.total_clients, 1)
    return render(
        request,
        "campaigns/detail.html",
        {
            "campaign": campaign,
            "clients": clients,
            "status": status,
            "rate": rate,
            "not_bought": campaign.total_clients - campaign.clients_with_sales,
            "unmatched": CampaignClient.objects.filter(campaign=campaign, client__isnull=True).count(),
            "today": date.today(),
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
        messages.error(request, _("Analysis end must be after the SMS send date."))
        return redirect("campaign_detail", pk=campaign.pk)
    typed = [
        CampaignRow(granit_client_id=item.granit_client_id, phone=item.phone)
        for item in campaign.campaign_clients.all()
    ]
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
    client_ids = list(
        campaign.campaign_clients.exclude(client_id=None).values_list("client_id", flat=True)
    )
    products = (
        _campaign_sales_qs(campaign)
        .filter(client_id__in=client_ids)
        .values("product__name", "product__granit_id", "product__group__name")
        .annotate(qty=Sum("quantity"), amount=Sum("amount"))
        .order_by("-amount")[:200]
    )
    return render(
        request,
        "campaigns/purchases.html",
        {"campaign": campaign, "products": products},
    )


def campaign_client_purchases(request, pk: int, row_pk: int):
    campaign = get_object_or_404(Campaign, pk=pk)
    row = get_object_or_404(CampaignClient, pk=row_pk, campaign=campaign)
    lines = []
    if row.client_id:
        lines = list(
            _campaign_sales_qs(campaign)
            .filter(client_id=row.client_id)
            .order_by("sale_date", "granit_sale_id", "granit_line_id")
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
        {"campaign": campaign, "row": row, "orders": orders},
    )
