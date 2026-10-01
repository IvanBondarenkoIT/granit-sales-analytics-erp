from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from core.models import Product, ProductGroup, Store
from sales.excel_matrix import matrix_to_xlsx
from sales.management.commands.seed_supergroups import ensure_catalog
from sales.matrix import build_matrix
from sales.models import SaleFact, SuperGroup, SuperGroupMember
from sales.supergroups import load_seed_config, resolve_supergroup_key


class SupergroupResolveTests(TestCase):
    def test_by_group_id_and_prefix(self):
        cfg = load_seed_config()
        self.assertEqual(resolve_supergroup_key(11077, "", config=cfg), "coffee_kg")
        self.assertEqual(resolve_supergroup_key(999, "DRINKS > Water > Still", config=cfg), "water")
        self.assertEqual(resolve_supergroup_key(999, "Cards Loyalty", config=cfg), "exclude")
        self.assertEqual(resolve_supergroup_key(999, "Something else", config=cfg), "unclassified")


class MatrixBalanceTests(TestCase):
    def setUp(self):
        self.store_a = Store.objects.create(granit_id=1, name="Shop A")
        self.store_b = Store.objects.create(granit_id=2, name="Shop B")
        self.g_coffee = ProductGroup.objects.create(granit_id=11077, name="Coffee kg")
        self.g_other = ProductGroup.objects.create(granit_id=99901, name="Misc")
        self.p1 = Product.objects.create(granit_id=101, name="Bean", group=self.g_coffee)
        self.p2 = Product.objects.create(granit_id=102, name="Other", group=self.g_other)
        self.p3 = Product.objects.create(granit_id=103, name="Orphan")  # no group
        coffee = SuperGroup.objects.create(key="coffee_kg", title="coffee kg", color="F4B183", sort_order=1)
        SuperGroup.objects.create(
            key="outside", title="Outside", color="FFFF00", sort_order=10000, is_catchall=True
        )
        SuperGroupMember.objects.create(super_group=coffee, product_group=self.g_coffee)
        SaleFact.objects.create(
            sale_date=date(2026, 9, 21),
            store=self.store_a,
            product=self.p1,
            quantity=Decimal("2"),
            amount=Decimal("100.00"),
            granit_sale_id=1,
            granit_line_id=1,
        )
        SaleFact.objects.create(
            sale_date=date(2026, 9, 22),
            store=self.store_b,
            product=self.p2,
            quantity=Decimal("1"),
            amount=Decimal("30.00"),
            granit_sale_id=2,
            granit_line_id=1,
        )
        SaleFact.objects.create(
            sale_date=date(2026, 9, 22),
            store=self.store_a,
            product=self.p3,
            quantity=Decimal("3"),
            amount=Decimal("15.00"),
            granit_sale_id=3,
            granit_line_id=1,
        )

    def test_matrix_totals_match_facts(self):
        matrix = build_matrix(date(2026, 9, 21), date(2026, 9, 22))
        self.assertTrue(matrix.balanced)
        self.assertEqual(matrix.grand.amount, Decimal("145.00"))
        self.assertEqual(matrix.fact_total.amount, Decimal("145.00"))
        titles = [r.title for r in matrix.rows]
        self.assertIn("coffee kg", titles)
        self.assertTrue(any(r.is_catchall for r in matrix.rows))
        catch = next(r for r in matrix.rows if r.is_catchall)
        self.assertEqual(catch.total.amount, Decimal("45.00"))

    def test_excel_export_bytes(self):
        from openpyxl import load_workbook
        from io import BytesIO

        matrix = build_matrix(date(2026, 9, 21), date(2026, 9, 22))
        data = matrix_to_xlsx(matrix)
        self.assertGreater(len(data), 100)
        self.assertEqual(data[:2], b"PK")
        wb = load_workbook(BytesIO(data))
        self.assertEqual(
            wb.sheetnames,
            ["Продажи", "Supergroups", "Unmapped", "Справочник групп", "Facts"],
        )
        sg = wb["Supergroups"]
        self.assertEqual(sg["A1"].value, "supergroup_key")
        self.assertIn("coffee kg", [c.value for c in sg["B"] if c.value])
        sales = wb["Продажи"]
        self.assertEqual(sales["A1"].value, "group_id")
        # last row is ИТОГО
        last = sales.max_row
        self.assertEqual(sales.cell(last, 2).value, "ИТОГО")


class SeedAndViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("analyst", password="test-pass-123")
        self.client.force_login(self.user)
        ProductGroup.objects.create(granit_id=11077, name="Coffee kg", parent_path="Coffee kg")
        drinks = ProductGroup.objects.create(granit_id=50000, name="DRINKS")
        ProductGroup.objects.create(granit_id=50001, name="Water", parent=drinks)

    def test_seed_assigns_by_id_and_prefix(self):
        stats = ensure_catalog(fill_unmapped=False)
        self.assertGreater(stats["created_sg"], 0)
        coffee = SuperGroup.objects.get(key="coffee_kg")
        water = SuperGroup.objects.get(key="water")
        self.assertTrue(SuperGroupMember.objects.filter(super_group=coffee, product_group__granit_id=11077).exists())
        self.assertTrue(SuperGroupMember.objects.filter(super_group=water, product_group__granit_id=50001).exists())
        # second plain seed refused by command, but ensure_catalog skips
        again = ensure_catalog(fill_unmapped=False)
        self.assertEqual(again["skipped"], 1)

    def test_matrix_page_ok(self):
        ensure_catalog()
        store = Store.objects.create(granit_id=1, name="Shop")
        product = Product.objects.create(granit_id=1, name="X", group=ProductGroup.objects.get(granit_id=11077))
        SaleFact.objects.create(
            sale_date=date(2026, 9, 21),
            store=store,
            product=product,
            quantity=1,
            amount=10,
            granit_sale_id=9,
            granit_line_id=1,
        )
        response = self.client.get(reverse("sales_matrix"), {"date_from": "2026-09-21", "date_to": "2026-09-21"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "coffee kg")

    def test_add_remove_member(self):
        ensure_catalog()
        sg = SuperGroup.objects.get(key="coffee_kg")
        other = ProductGroup.objects.create(granit_id=777, name="Loose")
        response = self.client.post(
            reverse("sales_matrix_sg", args=[sg.pk]) + "?date_from=2026-09-01&date_to=2026-09-30",
            {"action": "add", "group_id": "777"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SuperGroupMember.objects.filter(super_group=sg, product_group=other).exists())
        response = self.client.post(
            reverse("sales_matrix_sg", args=[sg.pk]) + "?date_from=2026-09-01&date_to=2026-09-30",
            {"action": "remove", "group_id": "777"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SuperGroupMember.objects.filter(product_group=other).exists())

    def test_set_group_owner(self):
        ensure_catalog()
        coffee = SuperGroup.objects.get(key="coffee_kg")
        water = SuperGroup.objects.get(key="water")
        group = ProductGroup.objects.create(granit_id=888, name="Reassign me")
        SuperGroupMember.objects.create(super_group=coffee, product_group=group)
        url = reverse("sales_matrix_group", args=[888]) + "?date_from=2026-09-01&date_to=2026-09-30"
        response = self.client.post(url, {"action": "set_owner", "sg_id": str(water.pk)})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SuperGroupMember.objects.filter(super_group=water, product_group=group).exists())
        response = self.client.post(url, {"action": "set_owner", "sg_id": "outside"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SuperGroupMember.objects.filter(product_group=group).exists())
        page = self.client.get(url)
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "name=\"sg_id\"")

    def test_move_super_group_order(self):
        ensure_catalog()
        url = reverse("sales_matrix_edit") + "?date_from=2026-09-01&date_to=2026-09-30"
        ordered = list(SuperGroup.objects.filter(is_catchall=False).order_by("sort_order", "title", "pk"))
        self.assertGreaterEqual(len(ordered), 2)
        first, second = ordered[0], ordered[1]
        response = self.client.post(url, {"action": "move_down", "sg_id": str(first.pk)})
        self.assertEqual(response.status_code, 302)
        reordered = list(SuperGroup.objects.filter(is_catchall=False).order_by("sort_order", "title", "pk"))
        self.assertEqual(reordered[0].pk, second.pk)
        self.assertEqual(reordered[1].pk, first.pk)
        response = self.client.post(url, {"action": "move_up", "sg_id": str(first.pk)})
        self.assertEqual(response.status_code, 302)
        restored = list(SuperGroup.objects.filter(is_catchall=False).order_by("sort_order", "title", "pk"))
        self.assertEqual(restored[0].pk, first.pk)