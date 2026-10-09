from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from core.models import SiteCategory, SiteProduct, Store
from etl.models import ETLRun
from etl.pipeline import (
    catalog_sync_running,
    last_catalog_run,
    load_sales_day,
    load_woo_catalog,
    nightly_reload_range,
    run_catalog_sync,
)
from etl.woo import _fetch_pages, parse_woo_category, parse_woo_product
from etl.queries import sql_invoices_day, sql_sales_day
from sales.models import SOURCE_INVOICE, SOURCE_RECEIPT, SaleFact


def fake_granit(sql, params=None):
    if "FROM STORGRPREF" in sql:
        return [{"STORID": 130, "GRPID": 33}]
    if "FROM STORLIST" in sql:
        return [{"ID": 130, "NAME": "BATUMIMALL"}, {"ID": 178, "NAME": "ХОРЕКА ТБИЛИСИ"}]
    if "FROM STORZAKAZDT" in sql:
        return [
            {"SALE_ID": 1, "LINE_ID": 1, "SALE_DATE": "2026-08-14T00:00:00", "STORE_ID": 33,
             "CLIENT_ID": None, "PRODUCT_ID": 20575, "QTY": 0.25, "AMOUNT": 30.0},
        ]
    if "FROM DGVDT" in sql:
        return [
            {"SALE_ID": 1, "LINE_ID": 1, "SALE_DATE": "2026-08-14T00:00:00", "WAREHOUSE_ID": 178,
             "CLIENT_ID": None, "PRODUCT_ID": 20628, "QTY": 5.0, "AMOUNT": 600.0},
            {"SALE_ID": 2, "LINE_ID": 7, "SALE_DATE": "2026-08-14T00:00:00", "WAREHOUSE_ID": 130,
             "CLIENT_ID": None, "PRODUCT_ID": 20575, "QTY": 1.0, "AMOUNT": 120.0},
        ]
    raise AssertionError(f"unexpected SQL: {sql[:80]}")


class SqlTests(TestCase):
    def test_retail_receipts_keep_payment_type_filter(self):
        sql, params = sql_sales_day()
        self.assertIn("CSDTKTHBID IN (?,?,?,?)", sql)
        self.assertEqual(params, [1, 2, 3, 5])

    def test_invoices_skip_receipt_linked_documents(self):
        sql, params = sql_invoices_day()
        self.assertIn("H.SZID IS NULL", sql)
        self.assertIn("LEFT JOIN GDDKT K", sql)
        self.assertEqual(params, [0])


class LoadSalesDayTests(TestCase):
    def setUp(self):
        Store.objects.create(granit_id=33, name="BatumiMall")

    @patch("etl.pipeline.query_rows", side_effect=fake_granit)
    def test_receipts_and_invoices_routed_to_stores(self, _query):
        self.assertEqual(load_sales_day(date(2026, 8, 14)), 3)

        receipt = SaleFact.objects.get(source=SOURCE_RECEIPT)
        self.assertEqual(receipt.store.granit_id, 33)
        self.assertEqual(receipt.quantity, Decimal("0.250"))

        horeca = SaleFact.objects.get(source=SOURCE_INVOICE, granit_sale_id=1)
        self.assertEqual(horeca.store.granit_id, 178)
        self.assertEqual(horeca.store.kind, Store.KIND_WAREHOUSE)
        self.assertEqual(horeca.store.name, "ХОРЕКА ТБИЛИСИ")

        mall_invoice = SaleFact.objects.get(source=SOURCE_INVOICE, granit_sale_id=2)
        self.assertEqual(mall_invoice.store.granit_id, 33)
        self.assertEqual(SaleFact.objects.retail().count(), 1)


class NightlyReloadRangeTests(TestCase):
    def test_two_full_months_back(self):
        self.assertEqual(
            nightly_reload_range(date(2026, 10, 2), 2), (date(2026, 8, 1), date(2026, 10, 2))
        )
        self.assertEqual(
            nightly_reload_range(date(2026, 11, 1), 2), (date(2026, 9, 1), date(2026, 11, 1))
        )

    def test_crosses_year(self):
        self.assertEqual(
            nightly_reload_range(date(2027, 1, 1), 2), (date(2026, 11, 1), date(2027, 1, 1))
        )

    def test_zero_months_is_yesterday_only(self):
        self.assertEqual(
            nightly_reload_range(date(2026, 10, 2), 0), (date(2026, 10, 1), date(2026, 10, 2))
        )

    @override_settings(ETL_RELOAD_MONTHS=1)
    def test_default_comes_from_settings(self):
        self.assertEqual(nightly_reload_range(date(2026, 10, 2))[0], date(2026, 9, 1))


class NightlyCommandTests(TestCase):
    @patch("etl.management.commands.etl_nightly.run_catalog_sync", return_value={})
    @patch("etl.management.commands.etl_nightly.load_stock", return_value={"rows": 0})
    @patch("etl.management.commands.etl_nightly.load_sales_range", return_value={"days": 1, "rows": 0})
    @patch("etl.management.commands.etl_nightly.load_dims", return_value={})
    @patch(
        "etl.management.commands.etl_nightly.nightly_reload_range",
        return_value=(date(2026, 8, 1), date(2026, 10, 2)),
    )
    def test_reloads_whole_window(self, _range, _dims, sales, _stock, catalog):
        call_command("etl_nightly", stdout=StringIO())
        sales.assert_called_once_with(date(2026, 8, 1), date(2026, 10, 2))
        catalog.assert_called_once()


class WooCatalogTests(TestCase):
    def test_parse_product_and_category(self):
        product = parse_woo_product(
            {"id": 7, "name": "[:ge]GE[:en]Machine EN[:]", "regular_price": "100",
             "sale_price": "", "categories": [{"id": 3}, {"id": 5}]}
        )
        self.assertEqual(product["name"], "Machine EN")
        self.assertEqual(product["category_ids"], ["3", "5"])
        self.assertIsNone(product["sale_price"])
        category = parse_woo_category({"id": 5, "name": "Dedica", "parent": 3, "count": 2})
        self.assertEqual(category["parent_id"], "3")

    def test_load_catalog_builds_tree_and_links(self):
        result = load_woo_catalog(
            products=[
                {"wp_product_id": "7", "name": "Machine", "category_ids": ["3", "5"]},
                {"wp_product_id": "8", "name": "Beans", "category_ids": ["9"]},
            ],
            categories=[
                {"wp_category_id": "3", "name": "Coffee machines", "parent_id": None},
                {"wp_category_id": "5", "name": "Dedica", "parent_id": "3"},
            ],
        )
        self.assertEqual(result, {"rows": 2, "categories": 2, "links": 2})
        child = SiteCategory.objects.get(wp_category_id="5")
        self.assertEqual(child.parent.wp_category_id, "3")
        machine = SiteProduct.objects.get(wp_product_id="7")
        self.assertEqual(machine.categories.count(), 2)


@override_settings(WOO_API_URL="https://shop.test/ge", WOO_API_KEY="ck_secret", WOO_API_SECRET="cs_secret")
class WooFetchErrorTests(SimpleTestCase):
    def _response(self, status, text="", headers=None):
        resp = requests.Response()
        resp.status_code = status
        resp._content = text.encode()
        resp.headers.update(headers or {})
        resp.url = "https://shop.test/ge/wp-json/wc/v3/products?consumer_key=ck_secret&consumer_secret=cs_secret"
        return resp

    def _error(self, **kwargs):
        with patch("etl.woo.requests.get", **kwargs):
            with self.assertRaises(RuntimeError) as ctx:
                _fetch_pages("products", {}, 100, 1)
        message = str(ctx.exception)
        self.assertNotIn("consumer_", message)
        self.assertNotIn("secret", message)
        return message

    def test_cloudflare_challenge_is_explicit(self):
        message = self._error(return_value=self._response(
            403, "<html><title>Just a moment...</title></html>", {"cf-mitigated": "challenge"}
        ))
        self.assertIn("Cloudflare challenge", message)

    def test_http_error_has_no_query_string(self):
        message = self._error(return_value=self._response(401, '{"code":"woocommerce_rest_cannot_view"}'))
        self.assertEqual(message, "Woo HTTP 401 on products page 1")

    def test_network_error_hides_url(self):
        message = self._error(side_effect=requests.ConnectionError(
            "Max retries exceeded with url: /ge/wp-json/wc/v3/products?consumer_key=ck_secret&consumer_secret=cs_secret"
        ))
        self.assertIn("ConnectionError", message)


class CatalogSyncTests(TestCase):
    def test_steps_run_even_if_one_fails(self):
        def broken():
            raise RuntimeError("sheets down")

        details = run_catalog_sync(
            loaders={
                "wp_mapping": broken,
                "woo_catalog": lambda: {"rows": 3},
                "product_costs": lambda: {"rows": 10},
            }
        )
        self.assertIn("error", details["wp_mapping"])
        self.assertEqual(details["woo_catalog"], {"rows": 3})
        run = last_catalog_run()
        self.assertEqual(run.status, "failed")
        self.assertEqual(run.records_processed, 13)
        self.assertFalse(catalog_sync_running())

    def test_running_detection(self):
        ETLRun.objects.create(etl_type="catalog", status="running")
        self.assertTrue(catalog_sync_running())
        with self.assertRaises(CommandError):
            call_command("sync_catalog", stdout=StringIO())
