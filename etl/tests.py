from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from core.models import Store
from etl.pipeline import load_sales_day
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
