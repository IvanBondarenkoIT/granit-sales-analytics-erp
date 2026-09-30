import io
from datetime import date
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from campaigns.analysis import analyze_rows
from campaigns.excel import CampaignRow
from campaigns.forms import CampaignUploadForm
from campaigns.models import Campaign, CampaignClient
from campaigns.tg_csv import parse_tg_users_csv
from core.models import Client, Product, Store
from etl.pipeline import card_number_from, upsert_clients
from sales.models import SaleFact


class TgCsvParserTests(TestCase):
    def test_no_header_dedupes_cards(self):
        text = "2200000093516,995557616822\n2211111309113,380666093340\n2200000093516,995557616822\n"
        rows = parse_tg_users_csv(io.StringIO(text))
        self.assertEqual([r.card_number for r in rows], ["2200000093516", "2211111309113"])
        self.assertEqual(rows[0].phone, "557616822")
        self.assertEqual(rows[1].phone, "380666093340")
        self.assertIsNone(rows[0].granit_client_id)

    def test_header_and_semicolon(self):
        data = "\ufeffcard;phone\n2200010008821;995579243074\nbad;1\n".encode("utf-8")
        rows = parse_tg_users_csv(io.BytesIO(data))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].card_number, "2200010008821")


class CardMatchTests(TestCase):
    def setUp(self):
        self.store = Store.objects.create(granit_id=1, name="Shop")
        self.product = Product.objects.create(granit_id=10, name="Coffee")
        self.client_a = Client.objects.create(granit_id=21238, name="Fedorov", card_number="2200000093516")

    def test_matches_by_card_and_sums_sales(self):
        SaleFact.objects.create(
            sale_date=date(2026, 9, 22),
            store=self.store,
            client=self.client_a,
            product=self.product,
            quantity=Decimal("1"),
            amount=Decimal("45.50"),
            granit_sale_id=1,
            granit_line_id=1,
        )
        campaign = Campaign.objects.create(name="TG", channel=Campaign.CHANNEL_TELEGRAM, sms_sent_on=date(2026, 9, 21))
        rows = [
            CampaignRow(granit_client_id=None, phone="557616822", card_number="2200000093516"),
            CampaignRow(granit_client_id=None, phone="", card_number="2299999999999"),
        ]
        analyze_rows(campaign, rows, date(2026, 9, 21), date(2026, 9, 30))
        campaign.refresh_from_db()
        self.assertEqual(campaign.total_clients, 2)
        self.assertEqual(campaign.clients_with_sales, 1)
        hit = CampaignClient.objects.get(campaign=campaign, card_number="2200000093516")
        self.assertEqual(hit.client, self.client_a)
        self.assertEqual(hit.granit_client_id, 21238)
        self.assertEqual(hit.sales_amount, Decimal("45.50"))
        miss = CampaignClient.objects.get(campaign=campaign, card_number="2299999999999")
        self.assertIsNone(miss.client)
        self.assertIsNone(miss.granit_client_id)


class EtlCardTests(TestCase):
    def test_only_13_digit_names_become_cards(self):
        self.assertEqual(card_number_from(" 2200000093516 "), "2200000093516")
        self.assertEqual(card_number_from("Ivan Petrov"), "")
        self.assertEqual(card_number_from("12345"), "")
        upsert_clients([{"CLIENT_ID": 5, "CLIENT_NAME": "Fedorov", "PHONE": "", "CARD_RAW": "2200000093516"}])
        self.assertEqual(Client.objects.get(granit_id=5).card_number, "2200000093516")


class UploadFormTests(TestCase):
    def _data(self, channel):
        return {"name": "TG 21.09", "channel": channel, "sms_sent_on": "2026-09-21", "date_to": "2026-09-30"}

    def test_telegram_requires_csv(self):
        form = CampaignUploadForm(
            self._data("telegram"),
            {"excel_file": SimpleUploadedFile("users.xlsx", b"x")},
        )
        self.assertFalse(form.is_valid())

    def test_telegram_csv_ok(self):
        form = CampaignUploadForm(
            self._data("telegram"),
            {"excel_file": SimpleUploadedFile("users.csv", b"2200000093516,995557616822\n")},
        )
        self.assertTrue(form.is_valid(), form.errors)


class TelegramUploadViewTests(TestCase):
    def setUp(self):
        user = get_user_model().objects.create_user("analyst", password="test-pass-123")
        self.client.force_login(user)
        Client.objects.create(granit_id=21238, name="Fedorov", card_number="2200000093516")

    @mock.patch("campaigns.analysis.backfill_clients_by_cards", return_value=0)
    def test_upload_creates_telegram_campaign(self, backfill):
        response = self.client.post(
            reverse("campaign_create"),
            {
                "name": "TG 21.09",
                "channel": "telegram",
                "sms_sent_on": "2026-09-21",
                "date_to": "2026-09-30",
                "excel_file": SimpleUploadedFile("users.csv", b"2200000093516,995557616822\n"),
            },
        )
        campaign = Campaign.objects.get(name="TG 21.09")
        self.assertRedirects(response, reverse("campaign_detail", args=[campaign.pk]))
        self.assertEqual(campaign.channel, Campaign.CHANNEL_TELEGRAM)
        self.assertEqual(campaign.campaign_clients.get().granit_client_id, 21238)
        backfill.assert_called_once()
