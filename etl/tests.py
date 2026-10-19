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
from etl.queries import sql_invoices_day, sql_realizations_day, sql_sales_day, sql_services_day
from sales.models import (
    SCOPE_ALL,
    SOURCE_INVOICE,
    SOURCE_REALIZED,
    SOURCE_RECEIPT,
    SOURCE_SERVICE,
    SaleFact,
)


def fake_granit(sql, params=None):
    if "FROM STORGRPREF" in sql:
        return [{"STORID": 130, "GRPID": 33}]
    if "FROM STORLIST" in sql:
        return [{"ID": 130, "NAME": "BATUMIMALL"}, {"ID": 178, "NAME": "ХОРЕКА ТБИЛИСИ"}]
    if "G.SZGDSID" in sql:
        return [
            {"SALE_ID": 1, "LINE_ID": 900, "SALE_DATE": "2026-08-14T00:00:00", "WAREHOUSE_ID": 130,
             "CLIENT_ID": None, "PRODUCT_ID": 20575, "QTY": 0.25, "AMOUNT": 29.6703296703},
        ]
    if "FROM STORZAKAZDT" in sql:
        return [
            {"SALE_ID": 1, "LINE_ID": 1, "SALE_DATE": "2026-08-14T00:00:00", "STORE_ID": 33,
             "CLIENT_ID": None, "PRODUCT_ID": 20575, "QTY": 0.25, "AMOUNT": 30.0},
        ]
    if "FROM HBGDDDU" in sql:
        return [{"ID": 1, "NAME": "ремонт кофеварки"}, {"ID": 2, "NAME": "Аренда кофеварки"}]
    if "JOIN GDDDTDDU" in sql:
        return [
            {"SALE_ID": 1, "LINE_ID": 1, "SALE_DATE": "2026-08-14T00:00:00", "WAREHOUSE_ID": 178,
             "CLIENT_ID": None, "SERVICE_ID": 1, "QTY": 1.0, "AMOUNT": 33.5},
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

    def test_realizations_link_receipt_lines(self):
        sql, params = sql_realizations_day()
        self.assertIn("H.SZID IS NOT NULL", sql)
        self.assertIn("S.ID = G.SZGDSID", sql)
        self.assertIn("H.SZID AS SALE_ID", sql)
        self.assertEqual(params, [0])

    def test_invoices_and_services_dated_by_realdate(self):
        for sql, _params in (sql_invoices_day(), sql_services_day(), sql_realizations_day()):
            self.assertIn("H.REALDATE >= ? AND H.REALDATE < ?", sql)
            self.assertIn("H.REALDATE AS SALE_DATE", sql)


class LoadSalesDayTests(TestCase):
    def setUp(self):
        Store.objects.create(granit_id=33, name="BatumiMall")

    @patch("etl.pipeline.query_rows", side_effect=fake_granit)
    def test_services_loaded_as_service_products(self, _query):
        load_sales_day(date(2026, 8, 14))
        line = SaleFact.objects.select_related("product__group").get(source=SOURCE_SERVICE)
        self.assertEqual(line.product.granit_id, -1)
        self.assertEqual(line.product.name, "Услуга: ремонт кофеварки")
        self.assertEqual(line.product.group.name, "Услуги")
        self.assertEqual(line.amount, Decimal("33.50"))
        self.assertEqual(line.store.granit_id, 178)
        self.assertFalse(SaleFact.objects.retail().filter(source=SOURCE_SERVICE).exists())

    @patch("etl.pipeline.query_rows", side_effect=fake_granit)
    def test_moved_document_replaces_old_day(self, _query):
        load_sales_day(date(2026, 8, 14))
        SaleFact.objects.filter(granit_sale_id=1, source__in=[SOURCE_INVOICE, SOURCE_SERVICE]).update(
            sale_date=date(2025, 8, 5)
        )
        load_sales_day(date(2026, 8, 14))
        self.assertFalse(SaleFact.objects.filter(sale_date=date(2025, 8, 5)).exists())
        self.assertEqual(SaleFact.objects.filter(granit_sale_id=1, source=SOURCE_INVOICE).count(), 1)

    @patch("etl.pipeline.query_rows", side_effect=fake_granit)
    def test_realized_receipt_lines_feed_all_warehouses(self, _query):
        load_sales_day(date(2026, 8, 14))
        realized = SaleFact.objects.get(source=SOURCE_REALIZED)
        self.assertEqual((realized.granit_sale_id, realized.granit_line_id), (1, 900))
        self.assertEqual(realized.store.granit_id, 33)
        self.assertEqual(realized.amount, Decimal("29.670330"))
        self.assertFalse(SaleFact.objects.for_scope(SCOPE_ALL).filter(source=SOURCE_RECEIPT).exists())
        self.assertFalse(SaleFact.objects.retail().filter(source=SOURCE_REALIZED).exists())

        SaleFact.objects.filter(source=SOURCE_REALIZED).update(sale_date=date(2026, 8, 13))
        load_sales_day(date(2026, 8, 14))
        self.assertEqual(SaleFact.objects.filter(source=SOURCE_REALIZED).count(), 1)
        self.assertFalse(SaleFact.objects.filter(sale_date=date(2026, 8, 13)).exists())

    @patch("etl.pipeline.query_rows", side_effect=fake_granit)
    def test_receipts_and_invoices_routed_to_stores(self, _query):
        self.assertEqual(load_sales_day(date(2026, 8, 14)), 5)

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
    @patch("etl.management.commands.etl_nightly.refresh_months", return_value=[])
    @patch("etl.management.commands.etl_nightly.run_catalog_sync", return_value={})
    @patch("etl.management.commands.etl_nightly.load_stock", return_value={"rows": 0})
    @patch("etl.management.commands.etl_nightly.load_sales_range", return_value={"days": 1, "rows": 0})
    @patch("etl.management.commands.etl_nightly.load_dims", return_value={})
    @patch(
        "etl.management.commands.etl_nightly.nightly_reload_range",
        return_value=(date(2026, 8, 1), date(2026, 10, 2)),
    )
    def test_reloads_whole_window(self, _range, _dims, sales, _stock, catalog, reconcile):
        call_command("etl_nightly", stdout=StringIO())
        sales.assert_called_once_with(date(2026, 8, 1), date(2026, 10, 2))
        catalog.assert_called_once()
        reconcile.assert_called_once()


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


def fake_reconcile(sql, params=None):
    if "FROM STORGRPREF" in sql:
        return [{"STORID": 130, "GRPID": 33}]
    if "FROM STORLIST" in sql:
        return [{"ID": 130, "NAME": "BATUMIMALL"}, {"ID": 133, "NAME": "СЦ ГРУЗИЯ"}]
    if "FROM HBGDDDU" in sql:
        return [{"ID": 1, "NAME": "ремонт кофеварки"}]
    if "TYP NOT IN" in sql:
        return [{"TYP": 1, "DOCS": 4, "AMOUNT": 500.0}]
    if "AS SZID" in sql:
        return [
            {"SALE_ID": 10, "NBR": "1", "DOC_DATE": "2026-08-03", "REAL_DATE": "2026-08-03", "SZID": None,
             "WAREHOUSE_ID": 133, "AMOUNT": 150.0, "GOODS": 40.0, "SERVICES": 100.0},
        ]
    if "JOIN GDDDTDDU" in sql:
        return [{"WAREHOUSE_ID": 133, "SERVICE_ID": 1, "AMOUNT": 100.0}]
    if "JOIN GDDDT G" in sql:
        return [{"WAREHOUSE_ID": 130, "AMOUNT": 100.0}, {"WAREHOUSE_ID": 133, "AMOUNT": 40.0}]
    if "SUM(H.SUMMA)" in sql:
        return [{"WAREHOUSE_ID": 130, "DOCS": 2, "AMOUNT": 100.0}, {"WAREHOUSE_ID": 133, "DOCS": 1, "AMOUNT": 150.0}]
    raise AssertionError(f"unexpected SQL: {sql[:80]}")


@patch("etl.reconcile.query_rows", side_effect=fake_reconcile)
@patch("etl.pipeline.query_rows", side_effect=fake_reconcile)
class ReconcileTests(TestCase):
    def setUp(self):
        from core.models import Product
        from etl.pipeline import upsert_service_products

        self.mall = Store.objects.create(granit_id=33, name="BatumiMall")
        self.sc = Store.objects.create(granit_id=133, name="СЦ ГРУЗИЯ", kind=Store.KIND_WAREHOUSE)
        self.coffee = Product.objects.create(granit_id=500, name="Coffee")
        self.repair = upsert_service_products([{"ID": 1, "NAME": "ремонт кофеварки"}])[1]
        self._fact(self.mall, self.coffee, SOURCE_RECEIPT, 1, "100")
        self._fact(self.mall, self.coffee, SOURCE_REALIZED, 1, "100")
        self._fact(self.mall, self.coffee, SOURCE_RECEIPT, 3, "7")
        self._fact(self.sc, self.coffee, SOURCE_INVOICE, 10, "40")
        self._fact(self.sc, self.repair, SOURCE_SERVICE, 10, "100")

    def _fact(self, store, product, source, sale_id, amount, day=date(2026, 8, 3)):
        SaleFact.objects.create(
            sale_date=day, source=source, store=store, product=product, quantity=1,
            amount=Decimal(amount), granit_sale_id=sale_id, granit_line_id=SaleFact.objects.count() + 1,
        )

    def test_components_leftover_and_diff(self, *_mocks):
        from etl.reconcile import build_month

        data = build_month(date(2026, 8, 1))
        by_store = {row["store"]: row for row in data["stores"]}
        self.assertEqual(by_store[33]["diff"], 0)
        self.assertEqual(by_store[33]["flags"], [])
        self.assertEqual(by_store[33]["pending"], 7.0)
        sc = by_store[133]
        self.assertEqual((sc["granit_goods"], sc["granit_services"], sc["leftover"]), (40.0, 100.0, 10.0))
        self.assertEqual(sc["ours_total"], 140.0)
        self.assertEqual(sc["diff"], -10.0)
        self.assertEqual(sorted(sc["flags"]), ["diff", "leftover"])
        self.assertEqual(data["services"][0]["name"], "ремонт кофеварки")
        self.assertFalse(data["services"][0]["new"])
        self.assertEqual(data["other_types"], [{"typ": 1, "docs": 4, "amount": 500.0}])

    def test_new_service_flag_when_history_exists(self, *_mocks):
        from etl.reconcile import build_month

        self._fact(self.mall, self.coffee, SOURCE_RECEIPT, 2, "5", day=date(2026, 7, 10))
        data = build_month(date(2026, 8, 1))
        self.assertTrue(data["services"][0]["new"])
        self.assertIn("new_service", [f["kind"] for f in data["flags"]])

    @patch("etl.reconcile.month_state", return_value="closed")
    def test_command_snapshot_and_exit_code(self, *_mocks):
        from etl.models import ReconcileSnapshot

        with self.assertRaises(CommandError):
            call_command("reconcile_sales", "--month", "2026-08", stdout=StringIO())
        snap = ReconcileSnapshot.objects.get(month=date(2026, 8, 1))
        self.assertEqual(snap.granit_total, Decimal("250.00"))
        self.assertEqual(snap.diff, Decimal("-10.00"))
        self.assertEqual(snap.flag_count, 2)

    @patch("etl.reconcile.month_state", return_value="open")
    def test_open_month_flags_do_not_fail(self, *_mocks):
        from etl.models import ReconcileSnapshot

        call_command("reconcile_sales", "--month", "2026-08", stdout=StringIO())
        snap = ReconcileSnapshot.objects.get(month=date(2026, 8, 1))
        self.assertEqual(snap.data["state"], "open")
        self.assertEqual(len(snap.data["flags"]), 2)
        self.assertEqual(snap.flag_count, 0)

    def test_month_state(self, *_mocks):
        from etl.reconcile import month_state

        self.assertEqual(month_state(date(2026, 8, 1), today=date(2026, 8, 20)), "open")
        self.assertEqual(month_state(date(2026, 8, 1), today=date(2026, 10, 1)), "partial")
        self._fact(self.mall, self.coffee, SOURCE_RECEIPT, 4, "1", day=date(2026, 7, 31))
        self.assertEqual(month_state(date(2026, 8, 1), today=date(2026, 10, 1)), "closed")

    def test_documents_drill_down(self, *_mocks):
        from etl.reconcile import month_documents

        docs = month_documents(date(2026, 8, 1), 133)
        self.assertEqual(docs["checked"], 1)
        row = docs["rows"][0]
        self.assertEqual((row["granit"], row["ours"], row["leftover"], row["diff"]), (150.0, 140.0, 10.0, -10.0))

class WpMappingGapsTests(TestCase):
    def test_report_splits_orphan_mapping_and_unmapped_site(self):
        from core.models import GranitWpMapping, Product, SiteProduct
        from etl.wp_mapping_report import build_mapping_gaps_report, write_mapping_gaps_xlsx
        from pathlib import Path
        import tempfile

        Product.objects.create(granit_id=26704, name="Opera BK")
        GranitWpMapping.objects.create(wp_product_id="7212", granit_id=26704)
        SiteProduct.objects.create(wp_product_id="8704", name="EC9555.BK", sku="EC9555.BK")
        GranitWpMapping.objects.create(wp_product_id="7832", granit_id=26910)
        SiteProduct.objects.create(wp_product_id="7832", name="EC9555.M")

        report = build_mapping_gaps_report()
        orphan_ids = {r.wp_product_id for r in report.mapping_without_site}
        unmapped_ids = {r.wp_product_id for r in report.site_without_mapping}
        self.assertIn("7212", orphan_ids)
        self.assertNotIn("7832", orphan_ids)
        self.assertIn("8704", unmapped_ids)
        self.assertNotIn("7832", unmapped_ids)

        with tempfile.TemporaryDirectory() as tmp:
            path = write_mapping_gaps_xlsx(report, Path(tmp) / "gaps.xlsx")
            self.assertTrue(path.exists())


class SheetsHeaderTests(SimpleTestCase):
    def test_header_column_indexes(self):
        from etl.sheets import _header_column_indexes

        wp_idx, granit_idx = _header_column_indexes(["wp-id", "name", "granit_id"])
        self.assertEqual((wp_idx, granit_idx), (0, 2))
