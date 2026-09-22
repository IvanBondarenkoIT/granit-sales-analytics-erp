"""Match campaign clients to sales in the analysis window."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from django.db.models import Sum
from django.utils.translation import gettext as _

from django.conf import settings

from campaigns.excel import CampaignRow, normalize_phone, parse_campaign_xlsx
from campaigns.models import Campaign, CampaignClient
from core.models import Client
from sales.models import SaleFact

DEFAULT_SMS_SENT_ON = date(2026, 9, 18)
LOCAL_SMS_XLSX = (
    Path(settings.BASE_DIR) / "data" / "local" / "ge_buyers_phones_2025-09_2026-09_final.xlsx"
)


def analyze_rows(
    campaign: Campaign,
    rows: list[CampaignRow],
    date_from: date,
    date_to: date,
) -> Campaign:
    """date_from inclusive, date_to exclusive."""
    if date_to <= date_from:
        raise ValueError("analysis end must be after start")

    clients_by_id = {
        c.granit_id: c
        for c in Client.objects.filter(granit_id__in=[r.granit_client_id for r in rows])
    }
    phone_index: dict[str, Client] = {}
    for client in Client.objects.exclude(phone=""):
        key = normalize_phone(client.phone)
        if key and key not in phone_index:
            phone_index[key] = client

    CampaignClient.objects.filter(campaign=campaign).delete()
    objects: list[CampaignClient] = []
    linked_ids: list[int] = []
    for row in rows:
        client = clients_by_id.get(row.granit_client_id)
        if client is None and row.phone:
            client = phone_index.get(row.phone)
        objects.append(
            CampaignClient(
                campaign=campaign,
                client=client,
                granit_client_id=row.granit_client_id,
                phone=row.phone,
            )
        )
        if client is not None:
            linked_ids.append(client.id)
    CampaignClient.objects.bulk_create(objects, batch_size=1000)

    totals = {
        row["client_id"]: row["amount"] or Decimal("0")
        for row in SaleFact.objects.filter(
            sale_date__gte=date_from,
            sale_date__lt=date_to,
            client_id__in=linked_ids,
        )
        .values("client_id")
        .annotate(amount=Sum("amount"))
    }

    bought = 0
    to_update: list[CampaignClient] = []
    for item in CampaignClient.objects.filter(campaign=campaign).select_related("client"):
        if item.client_id and item.client_id in totals:
            item.had_sales = True
            item.sales_amount = totals[item.client_id]
            bought += 1
            to_update.append(item)
    if to_update:
        CampaignClient.objects.bulk_update(to_update, ["had_sales", "sales_amount"], batch_size=1000)

    campaign.analysis_period_start = date_from
    campaign.analysis_period_end = date_to
    campaign.total_clients = len(rows)
    campaign.clients_with_sales = bought
    campaign.save()
    return campaign


def import_campaign_from_path(
    path: str | Path,
    *,
    name: str,
    date_from: date,
    date_to: date,
    notes: str = "",
) -> Campaign:
    path = Path(path)
    rows = parse_campaign_xlsx(path)
    if not rows:
        raise ValueError(_("Excel has no client rows"))
    campaign = Campaign.objects.create(
        name=name,
        analysis_period_start=date_from,
        analysis_period_end=date_to,
        notes=notes,
    )
    return analyze_rows(campaign, rows, date_from, date_to)
