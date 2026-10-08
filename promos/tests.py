from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import (
    GranitWpMapping,
    Product,
    ProductCostSnapshot,
    ProductGroup,
    SiteCategory,
    SiteProduct,
    Store,
)
from etl.models import ETLRun
from etl.sheets import parse_granit_sheet_rows
from etl.woo import clean_product_name
from promos.analysis import analyze_promo
from promos.charts import POST_DAYS, build_promo_charts
from promos.models import Promo, PromoProduct
from promos.pricing import build_promo_price_rows
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

    def test_baseline_is_mean_with_zero_days(self):
        SaleFact.objects.filter(sale_date__in=[date(2026, 8, 4), date(2026, 8, 6), date(2026, 8, 8)]).delete()
        SaleFact.objects.filter(sale_date__in=[date(2026, 8, 3), date(2026, 8, 5), date(2026, 8, 7)]).update(
            amount=Decimal("0")
        )
        analyze_promo(self.promo)
        row = self.promo.analyses.first()
        self.assertEqual(row.baseline_pre_period, Decimal("14.29"))

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


class PromoListTabsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tabs", password="test-pass-123")
        self.client.force_login(self.user)
        today = date.today()
        Promo.objects.create(name="Live", start_date=today - timedelta(days=1), end_date=today + timedelta(days=5))
        Promo.objects.create(name="Old", start_date=today - timedelta(days=40), end_date=today - timedelta(days=10))

    def test_active_and_passed_tabs(self):
        active = self.client.get(reverse("promo_list") + "?tab=active")
        self.assertContains(active, "Live")
        self.assertNotContains(active, "Old")
        passed = self.client.get(reverse("promo_list") + "?tab=passed")
        self.assertContains(passed, "Old")
        self.assertNotContains(passed, "Live")


class PromoPricingTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("price", password="test-pass-123")
        self.client.force_login(self.user)
        self.store = Store.objects.create(granit_id=33, name="Mall")
        self.product = Product.objects.create(granit_id=26212, name="ECAM450.65.S")
        GranitWpMapping.objects.create(wp_product_id="6219", granit_id=26212)
        SiteProduct.objects.create(
            wp_product_id="6219",
            name="Site ECAM",
            sku="ECAM450.65.S",
            regular_price=Decimal("3599.00"),
            sale_price=Decimal("2154.00"),
        )
        ProductCostSnapshot.objects.create(
            product=self.product,
            snapshot_date=date.today() - timedelta(days=1),
            last_cost=Decimal("1702.00"),
            avg_cost_90d=Decimal("1900.00"),
            stock_qty=Decimal("2"),
        )
        self.promo = Promo.objects.create(
            name="Autumn",
            start_date=date.today() - timedelta(days=3),
            end_date=date.today() + timedelta(days=3),
        )
        PromoProduct.objects.create(promo=self.promo, product=self.product)
        SaleFact.objects.create(
            sale_date=date.today(),
            store=self.store,
            product=self.product,
            quantity=1,
            amount=Decimal("2000.00"),
            granit_sale_id=1,
            granit_line_id=1,
        )

    def test_margin_and_earnings(self):
        rows = build_promo_price_rows(self.promo)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row.sale_price, Decimal("2154.00"))
        self.assertEqual(row.last_cost, Decimal("1702.00"))
        self.assertEqual(row.stock_qty, Decimal("2"))
        self.assertEqual(row.estimated_earnings, Decimal("904.00"))  # (2154-1702)*2
        self.assertIsNotNone(row.margin_pct)
        self.assertEqual(row.sale_compare, Decimal("2000.00"))  # fact avg differs

    def test_detail_shows_price_table(self):
        response = self.client.get(reverse("promo_detail", args=[self.promo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2154")
        self.assertContains(response, "1702")
        self.assertContains(response, "904")



class PromoPickerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("picker", password="test-pass-123")
        self.client.force_login(self.user)
        self.root = ProductGroup.objects.create(granit_id=1, name="Coffee machines")
        self.child = ProductGroup.objects.create(granit_id=2, name="Delonghi", parent=self.root)
        self.ecam = Product.objects.create(granit_id=26212, name="ECAM450", group=self.child)
        self.dedica = Product.objects.create(granit_id=24313, name="EC685.M", group=self.root)
        Product.objects.create(granit_id=1, name="Old ECAM", group=self.child, is_active=False)
        cat = SiteCategory.objects.create(wp_category_id="10", name="Espresso")
        linked = SiteProduct.objects.create(wp_product_id="6219", name="Site ECAM", sale_price=Decimal("2154"))
        unlinked = SiteProduct.objects.create(wp_product_id="9999", name="Site orphan")
        linked.categories.add(cat)
        unlinked.categories.add(cat)
        GranitWpMapping.objects.create(wp_product_id="6219", granit_id=26212)
        self.cat = cat

    def test_group_tree_children(self):
        response = self.client.get(reverse("picker_granit_groups"))
        self.assertContains(response, "Coffee machines")
        self.assertNotContains(response, "Delonghi")
        response = self.client.get(reverse("picker_granit_groups"), {"parent": self.root.pk})
        self.assertContains(response, "Delonghi")

    def test_group_products_include_subgroups_and_skip_inactive(self):
        response = self.client.get(reverse("picker_granit_products"), {"group": self.root.pk})
        self.assertContains(response, "ECAM450")
        self.assertContains(response, "EC685.M")
        self.assertContains(response, "Site ECAM")
        self.assertNotContains(response, "Old ECAM")
        data = self.client.get(
            reverse("picker_granit_all"), {"group": self.root.pk, "inactive": "1"}
        ).json()
        self.assertEqual(len(data["items"]), 3)
        direct = self.client.get(
            reverse("picker_granit_all"), {"group": self.root.pk, "direct": "1"}
        ).json()
        self.assertEqual([i["name"] for i in direct["items"]], ["EC685.M"])

    def test_site_products_unlinked_disabled(self):
        response = self.client.get(reverse("picker_site_products"), {"category": self.cat.pk})
        self.assertContains(response, f'value="{self.ecam.pk}"')
        self.assertContains(response, "Site orphan")
        self.assertContains(response, "disabled")
        data = self.client.get(reverse("picker_site_all"), {"category": self.cat.pk}).json()
        self.assertEqual([i["pk"] for i in data["items"]], [self.ecam.pk])

    def test_create_with_several_products(self):
        response = self.client.post(
            reverse("promo_create"),
            {
                "name": "Multi",
                "start_date": "2026-10-01",
                "end_date": "2026-10-10",
                "pre_period_days": 14,
                "product_ids": [self.ecam.pk, self.dedica.pk, self.ecam.pk],
            },
        )
        promo = Promo.objects.get(name="Multi")
        self.assertRedirects(response, reverse("promo_detail", args=[promo.pk]))
        self.assertEqual(
            sorted(promo.promo_products.values_list("product_id", flat=True)),
            sorted([self.ecam.pk, self.dedica.pk]),
        )

    def test_edit_keeps_manual_price_and_legacy_group(self):
        promo = Promo.objects.create(name="Edit me", start_date=date(2026, 10, 1), end_date=date(2026, 10, 5))
        PromoProduct.objects.create(promo=promo, product=self.ecam, manual_sale_price=Decimal("1999"))
        PromoProduct.objects.create(promo=promo, product=self.dedica)
        PromoProduct.objects.create(promo=promo, product_group=self.child)
        page = self.client.get(reverse("promo_edit", args=[promo.pk]))
        self.assertContains(page, 'name="group_ids"')
        self.assertContains(page, f'name="product_ids" value="{self.ecam.pk}"')
        self.client.post(
            reverse("promo_edit", args=[promo.pk]),
            {
                "name": "Edited",
                "start_date": "2026-10-01",
                "end_date": "2026-10-06",
                "pre_period_days": 7,
                "product_ids": [self.ecam.pk],
                "group_ids": [self.child.pk],
            },
        )
        promo.refresh_from_db()
        self.assertEqual(promo.name, "Edited")
        rows = list(promo.promo_products.all())
        self.assertEqual(len(rows), 2)
        kept = next(r for r in rows if r.product_id == self.ecam.pk)
        self.assertEqual(kept.manual_sale_price, Decimal("1999.00"))
        self.assertTrue(any(r.product_group_id == self.child.pk for r in rows))


class CatalogSyncButtonTests(TestCase):
    def test_only_staff_can_start(self):
        user = get_user_model().objects.create_user("plain", password="test-pass-123")
        self.client.force_login(user)
        with patch("promos.views.subprocess.Popen") as popen:
            response = self.client.post(reverse("promo_sync_catalog"))
        self.assertEqual(response.status_code, 403)
        popen.assert_not_called()

    def test_staff_starts_once(self):
        user = get_user_model().objects.create_user("boss", password="test-pass-123", is_staff=True)
        self.client.force_login(user)
        with patch("promos.views.subprocess.Popen") as popen:
            response = self.client.post(reverse("promo_sync_catalog"), {"next": "/promos/"})
        self.assertRedirects(response, "/promos/", fetch_redirect_response=False)
        popen.assert_called_once()
        ETLRun.objects.create(etl_type="catalog", status="running")
        with patch("promos.views.subprocess.Popen") as popen:
            self.client.post(reverse("promo_sync_catalog"))
        popen.assert_not_called()
        page = self.client.get(reverse("promo_list"))
        self.assertTrue(page.context["catalog"]["running"])
        self.assertNotContains(page, reverse("promo_sync_catalog"))


class MappingParseTests(TestCase):
    def test_parse_granit_sheet_rows(self):
        pairs = parse_granit_sheet_rows(
            [{"wp-id": "6219", "granit_id": "26212"}, {"wp-id": "", "granit_id": "1"}]
        )
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0].wp_product_id, "6219")
        self.assertEqual(pairs[0].granit_id, 26212)

    def test_clean_qtranslate_product_name(self):
        self.assertEqual(
            clean_product_name("[:ge]DeLonghi EC890 GE[:en]DeLonghi EC890 EN [:]"),
            "DeLonghi EC890 EN",
        )
        self.assertEqual(clean_product_name("Plain &amp; simple"), "Plain & simple")
