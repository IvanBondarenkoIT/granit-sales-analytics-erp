from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from campaigns.analysis import (
    DEFAULT_SMS_SENT_ON,
    LOCAL_SMS_XLSX,
    analyze_rows,
    import_campaign_from_path,
)
from campaigns.excel import parse_campaign_xlsx
from campaigns.forms import CampaignUploadForm
from campaigns.models import Campaign, CampaignClient


def campaign_list(request):
    campaigns = Campaign.objects.all()
    return render(request, "campaigns/list.html", {"campaigns": campaigns})


def campaign_create(request):
    if request.method == "POST":
        form = CampaignUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                if form.cleaned_data["use_local_file"] and LOCAL_SMS_XLSX.is_file():
                    campaign = import_campaign_from_path(
                        LOCAL_SMS_XLSX,
                        name=form.cleaned_data["name"],
                        date_from=form.cleaned_data["date_from"],
                        date_to=form.cleaned_data["date_to"],
                        notes=form.cleaned_data["notes"]
                        or _("SMS sent on %(date)s") % {"date": DEFAULT_SMS_SENT_ON.isoformat()},
                    )
                else:
                    upload = form.cleaned_data["excel_file"]
                    rows = parse_campaign_xlsx(upload)
                    campaign = Campaign.objects.create(
                        name=form.cleaned_data["name"],
                        notes=form.cleaned_data["notes"],
                    )
                    if upload:
                        campaign.uploaded_file.save(upload.name, upload, save=True)
                    campaign = analyze_rows(
                        campaign,
                        rows,
                        form.cleaned_data["date_from"],
                        form.cleaned_data["date_to"],
                    )
            except Exception as exc:
                messages.error(request, str(exc))
            else:
                messages.success(request, _("Campaign analyzed."))
                return redirect("campaign_detail", pk=campaign.pk)
    else:
        form = CampaignUploadForm(
            initial={
                "name": _("SMS 18 Sep 2026"),
                "notes": _("SMS sent on %(date)s") % {"date": DEFAULT_SMS_SENT_ON.isoformat()},
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
        },
    )
