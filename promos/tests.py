from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Product, ProductGroup, Store
from promos.analysis import analyze_promo
from promos.charts import POST_DAYS, build_promo_charts
from promos.models import Promo, PromoProduct
from sales.models import SaleFact

LABELS = {"actual": "Actual", "baseline": "Baseline", "yoy": "Last year", "forecast": "Forecast"}


class PromoChartsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("analyst", password="test-pass-123")
        self.client.force_login(self.user)
        self.store = Store.objects.create(granit_id=1, name="Shop")
        group = ProductGroup.objects.create(granit_id=10, name="Candies")
        self.product = Product.objects.create(granit_id=100, name="Candy", group=group)
        self.promo = Promo.objects.create(
            name="Candy week",
            start_date=date(2026, 8, 10),
            end_date=date(2026, 8, 16),
            pre_period_days=7,
        )
        PromoProduct.objects.create(promo=self.promo, product=self.product)
        line = 0
        day = date(2026, 8, 1)
        while day <= date(2026, 8, 25):
            amount = Decimal("150") if self.promo.start_date <= day <= self.promo.end_date else Decimal("100")
            line += 1
            SaleFact.objects.create(
                sale_date=day,
                store=self.store,
                product=self.product,
                quantity=1,
                amount=amount,
                granit_sale_id=line,
                granit_line_id=1,
            )
            day += timedelta(days=1)
        analyze_promo(self.promo)

    def test_cumulative_matches_card_numbers(self):
        charts = build_promo_charts(self.promo, LABELS)
        self.assertFalse(charts["empty"])
        kpi = charts["kpi"]
        self.assertEqual(kpi["actual_sum"], Decimal("1050"))
        self.assertEqual(kpi["baseline_sum"], Decimal("700"))
        self.assertEqual(kpi["incremental"], Decimal("350"))
        cumulative = charts["cumulative"]
        self.assertEqual(cumulative["diff"], kpi["actual_sum"] - kpi["baseline_sum"])
        self.assertTrue(cumulative["positive"])

    def test_daily_window_and_forecast_only_in_promo(self):
        charts = build_promo_charts(self.promo, LABELS)
        series = charts["daily"]["series"]
        expected_days = self.promo.pre_period_days + 7 + POST_DAYS
        self.assertEqual(len(series["days"]), expected_days)
        for day, value in zip(series["days"], series["forecast"]):
            if not (self.promo.start_date <= day <= self.promo.end_date):
                self.assertIsNone(value)
        self.assertTrue(charts["daily"]["has_baseline"])

    def test_charts_page_renders_svg(self):
        response = self.client.get(reverse("promo_charts", args=[self.promo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<svg")
        detail = self.client.get(reverse("promo_detail", args=[self.promo.pk]))
        self.assertContains(detail, reverse("promo_charts", args=[self.promo.pk]))

    def test_svg_coordinates_not_localized(self):
        import re

        from django.utils import translation

        with translation.override("ru"):
            response = self.client.get(
                reverse("promo_charts", args=[self.promo.pk]), HTTP_ACCEPT_LANGUAGE="ru"
            )
        html = response.content.decode()
        for attr in re.findall(r'\s(?:x|y|width|height|cx|cy)="([^"]*)"', html):
            self.assertNotIn(",", attr)

    def test_empty_promo_page(self):
        empty = Promo.objects.create(
            name="Future",
            start_date=date(2027, 1, 1),
            end_date=date(2027, 1, 5),
        )
        self.assertTrue(build_promo_charts(empty, LABELS)["empty"])
        response = self.client.get(reverse("promo_charts", args=[empty.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "<svg class=\"chart\"")
