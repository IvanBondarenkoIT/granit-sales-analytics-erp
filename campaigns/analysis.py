"""Match campaign clients to sales in the analysis window."""
from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.db.models import Sum
from django.utils.translation import gettext as _

from django.conf import settings

from campaigns.excel import CampaignRow, normalize_phone, parse_campaign_xlsx
from campaigns.models import Campaign, CampaignClient
from campaigns.tg_csv import parse_tg_users_csv
from core.models import Client
from etl.pipeline import backfill_clients_by_cards
from etl.proxy import ProxyApiError
from sales.models import SaleFact

logger = logging.getLogger(__name__)

DEFAULT_SMS_SENT_ON = date(2026, 9, 18)
LOCAL_SMS_XLSX = (
    Path(settings.BASE_DIR) / "data" / "local" / "ge_buyers_phones_2025-09_2026-09_final.xlsx"
)


def prefetch_card_clients(rows: list[CampaignRow]) -> None:
    """Pull clients for cards missing locally; keep going with local data if proxy is down."""
    cards = [r.card_number for r in rows if r.card_number]
    if not cards:
        return
    try:
        backfill_clients_by_cards(cards)
    except ProxyApiError as exc:
        logger.warning("card backfill skipped: %s", exc)


def analyze_rows(
    campaign: Campaign,
    rows: list[CampaignRow],
    date_from: date,
    date_to: date,
) -> Campaign:
    """date_from inclusive, date_to exclusive. Match order: granit id, card, phone."""
    if date_to <= date_from:
        raise ValueError("analysis end must be after start")

    ids = [r.granit_client_id for r in rows if r.granit_client_id is not None]
    clients_by_id = {c.granit_id: c for c in Client.objects.filter(granit_id__in=ids)}
    cards = [r.card_number for r in rows if r.card_number]
    clients_by_card = {c.card_number: c for c in Client.objects.filter(card_number__in=cards)}
    phone_index: dict[str, Client] = {}
    for client in Client.objects.exclude(phone=""):
        key = normalize_phone(client.phone)
        if key and key not in phone_index:
            phone_index[key] = client

    CampaignClient.objects.filter(campaign=campaign).delete()
    objects: list[CampaignClient] = []
    linked_ids: list[int] = []
    used_granit_ids: set[int] = set()
    for row in rows:
        client = None
        if row.granit_client_id is not None:
            client = clients_by_id.get(row.granit_client_id)
        if client is None and row.card_number:
            client = clients_by_card.get(row.card_number)
        if client is None and row.phone:
            client = phone_index.get(row.phone)
        granit_id = row.granit_client_id
        if granit_id is None and client is not None:
            granit_id = client.granit_id
        if granit_id is not None:
            if granit_id in used_granit_ids:
                continue
            used_granit_ids.add(granit_id)
        objects.append(
            CampaignClient(
                campaign=campaign,
                client=client,
                granit_client_id=granit_id,
                card_number=row.card_number,
                phone=row.phone,
            )
        )
        if client is not None:
            linked_ids.append(client.id)
    CampaignClient.objects.bulk_create(objects, batch_size=1000)

    totals = {
        row["client_id"]: row["amount"] or Decimal("0")
        for row in SaleFact.objects.retail().filter(
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

    campaign.sms_sent_on = campaign.sms_sent_on or date_from
    campaign.analysis_period_start = date_from
    campaign.analysis_period_end = date_to
    campaign.total_clients = len(objects)
    campaign.clients_with_sales = bought
    campaign.save()
    return campaign


def import_campaign_from_path(
    path: str | Path,
    *,
    name: str,
    date_from: date,
    date_to: date,
    sms_sent_on: date | None = None,
    notes: str = "",
) -> Campaign:
    path = Path(path)
    rows = parse_campaign_xlsx(path)
    if not rows:
        raise ValueError(_("Excel has no client rows"))
    sent = sms_sent_on or date_from
    campaign = Campaign.objects.create(
        name=name,
        sms_sent_on=sent,
        analysis_period_start=date_from,
        analysis_period_end=date_to,
        notes=notes,
    )
    return analyze_rows(campaign, rows, date_from, date_to)


def import_tg_campaign_from_path(
    path: str | Path,
    *,
    name: str,
    sent_on: date,
    date_to: date,
    notes: str = "",
) -> Campaign:
    rows = parse_tg_users_csv(Path(path))
    if not rows:
        raise ValueError(_("CSV has no card rows"))
    prefetch_card_clients(rows)
    campaign = Campaign.objects.create(
        name=name,
        channel=Campaign.CHANNEL_TELEGRAM,
        sms_sent_on=sent_on,
        analysis_period_start=sent_on,
        analysis_period_end=date_to,
        notes=notes,
    )
    return analyze_rows(campaign, rows, sent_on, date_to)
