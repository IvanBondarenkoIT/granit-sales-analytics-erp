"""Deterministic local UI demo data for mobile-first screenshots (DEBUG only)."""
from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from campaigns.analysis import analyze_rows
from campaigns.excel import CampaignRow
from campaigns.models import Campaign
from core.models import (
    Client,
    GranitWpMapping,
    Product,
    ProductCostSnapshot,
    ProductGroup,
    ProductParameter,
    ProductParameterValue,
    SiteProduct,
    Store,
    StoreWarehouseLink,
)
from etl.models import ReconcileSnapshot
from promos.analysis import analyze_promo
from promos.models import Promo, PromoProduct
from sales.management.commands.seed_supergroups import ensure_catalog
from sales.models import (
    SOURCE_INVOICE,
    SOURCE_REALIZED,
    SOURCE_RECEIPT,
    SOURCE_SERVICE,
    SaleFact,
    StockSnapshot,
    SuperGroup,
    SuperGroupMember,
)

SEED = 20261124
DEFAULT_PASSWORD = "demo-pass-123"
# Compose service name + local loopback only. Anything else needs --allow-host.
SAFE_DB_HOSTS = {"db", "localhost", "127.0.0.1", "::1", ""}


def _db_has_business_data() -> bool:
    return any(
        (
            Store.objects.exists(),
            Product.objects.exists(),
            SaleFact.objects.exists(),
            Campaign.objects.exists(),
            Promo.objects.exists(),
            SuperGroup.objects.exists(),
            ReconcileSnapshot.objects.exists(),
            Client.objects.exists(),
        )
    )


def _wipe() -> None:
    SaleFact.objects.all().delete()
    StockSnapshot.objects.all().delete()
    from campaigns.models import CampaignClient

    CampaignClient.objects.all().delete()
    Campaign.objects.all().delete()
    from promos.models import PromoAnalysis

    PromoAnalysis.objects.all().delete()
    PromoProduct.objects.all().delete()
    Promo.objects.all().delete()
    ReconcileSnapshot.objects.all().delete()
    SuperGroupMember.objects.all().delete()
    SuperGroup.objects.all().delete()
    ProductCostSnapshot.objects.all().delete()
    SiteProduct.objects.all().delete()
    GranitWpMapping.objects.all().delete()
    Product.objects.all().delete()
    ProductGroup.objects.all().delete()
    ProductParameterValue.objects.all().delete()
    ProductParameter.objects.all().delete()
    Client.objects.all().delete()
    StoreWarehouseLink.objects.all().delete()
    Store.objects.all().delete()


class Command(BaseCommand):
    help = "Seed deterministic demo data for local UI screenshots (requires DEBUG)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Wipe business data and re-seed even if the DB is not empty",
        )
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Password for demo_staff / demo_user (default: {DEFAULT_PASSWORD})",
        )
        parser.add_argument(
            "--allow-host",
            default=None,
            metavar="HOST",
            help=(
                "Allow seeding against this DB HOST when it is not a local/compose host "
                f"(safe defaults include: db, localhost, 127.0.0.1)"
            ),
        )

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_ui_demo refuses to run when DEBUG=False")

        db = settings.DATABASES["default"]
        host = str(db.get("HOST") or "")
        name = db.get("NAME")
        allow_host = options.get("allow_host")
        if host not in SAFE_DB_HOSTS and host != allow_host:
            raise CommandError(
                "seed_ui_demo refuses non-local DB host "
                f"{host!r} (database={name!r}). "
                f"Allowed hosts: {sorted(SAFE_DB_HOSTS)!r}. "
                f"Pass --allow-host {host} only if you intentionally target that server."
            )

        if _db_has_business_data() and not options["force"]:
            raise CommandError(
                "Database already has business data. Use --force to wipe and re-seed "
                f"(local only; current target host={host!r} name={name!r})."
            )

        self.stdout.write(f"Seeding UI demo into host={host!r} name={name!r}…")
        with transaction.atomic():
            if options["force"] and _db_has_business_data():
                self.stdout.write("Wiping existing business data (--force)…")
                _wipe()
            stats = self._seed(password=options["password"])

        self.stdout.write(self.style.SUCCESS(f"seed_ui_demo: {stats}"))

    def _seed(self, *, password: str) -> dict:
        rng = random.Random(SEED)
        today = date.today()
        User = get_user_model()

        staff, _ = User.objects.update_or_create(
            username="demo_staff",
            defaults={"is_staff": True, "is_superuser": False, "email": "demo_staff@example.com"},
        )
        staff.set_password(password)
        staff.save()
        user, _ = User.objects.update_or_create(
            username="demo_user",
            defaults={"is_staff": False, "is_superuser": False, "email": "demo_user@example.com"},
        )
        user.set_password(password)
        user.save()

        stores = self._stores()
        param, param_values = self._parameter()
        groups, products = self._catalog(param, param_values)
        ensure_catalog(fill_unmapped=False)
        clients = self._clients(rng)
        sales_n = self._sales(rng, today, stores, products, clients)
        stock_n = self._stock(today, stores, products, rng)
        reconcile_n = self._reconcile(today, stores)
        campaigns_n = self._campaigns(rng, today, stores, products, clients)
        promos_n = self._promos(rng, today, stores, products, groups)

        return {
            "stores": len(stores),
            "products": len(products),
            "sales": sales_n,
            "stock": stock_n,
            "reconcile_months": reconcile_n,
            "campaigns": campaigns_n,
            "promos": promos_n,
            "supergroups": SuperGroup.objects.count(),
            "users": "demo_staff,demo_user",
        }

    def _stores(self) -> list[Store]:
        specs = [
            (33, "Batumi Mall", Store.KIND_GROUP),
            (41, "Vake Gallery Coffee & More Flagship Store", Store.KIND_GROUP),
            (55, "Saburtalo Retail", Store.KIND_GROUP),
            (133, "СЦ ГРУЗИЯ", Store.KIND_GROUP),
            (178, "HORECA TBILISI", Store.KIND_WAREHOUSE),
        ]
        stores = []
        for gid, name, kind in specs:
            store, _ = Store.objects.update_or_create(
                granit_id=gid, defaults={"name": name, "kind": kind}
            )
            stores.append(store)
        retail = next(s for s in stores if s.granit_id == 33)
        horeca = next(s for s in stores if s.granit_id == 178)
        StoreWarehouseLink.objects.update_or_create(
            warehouse=horeca, defaults={"receipt_group": retail}
        )
        return stores

    def _parameter(self) -> tuple[ProductParameter, list[ProductParameterValue]]:
        param, _ = ProductParameter.objects.update_or_create(
            granit_id=2, defaults={"name": "продукция"}
        )
        values = []
        for vid, label in ((201, "зерно"), (202, "машина"), (203, "прочее")):
            val, _ = ProductParameterValue.objects.update_or_create(
                granit_id=vid, defaults={"parameter": param, "label": label}
            )
            values.append(val)
        return param, values

    def _catalog(
        self, param: ProductParameter, values: list[ProductParameterValue]
    ) -> tuple[list[ProductGroup], list[Product]]:
        group_specs = [
            (11077, "Coffee kg", None),
            (21270, "Coffee makers", None),
            (25539, "Drinks Espresso RTD", None),
            (26761, "Cleaning tablets and liquids for espresso", None),
            (99901, "Misc unclassified demo", None),
        ]
        groups: list[ProductGroup] = []
        for gid, name, parent in group_specs:
            g, _ = ProductGroup.objects.update_or_create(
                granit_id=gid, defaults={"name": name, "parent": parent}
            )
            groups.append(g)

        by_gid = {g.granit_id: g for g in groups}
        product_specs = [
            (101, "Ethiopia Yirgacheffe washed Grade 1 1kg bag", 11077, True, values[0]),
            (102, "Brazil Santos medium roast 250g", 11077, True, values[0]),
            (26212, "De’Longhi ECAM450.65.S Eletta Explore", 21270, False, values[1]),
            (24313, "De’Longhi Dedica EC685.M", 21270, False, values[1]),
            (301, "Ready espresso can 250ml long promotional name for wrapping", 25539, False, values[2]),
            (401, "Cleaning tablet 10-pack", 26761, False, values[2]),
            (501, "Orphan demo SKU without group mapping", None, False, values[2]),
        ]
        products: list[Product] = []
        for gid, name, group_id, _weight, pval in product_specs:
            product, _ = Product.objects.update_or_create(
                granit_id=gid,
                defaults={
                    "name": name,
                    "group": by_gid.get(group_id) if group_id else None,
                    "parameter": param,
                    "parameter_value": pval,
                    "is_active": True,
                },
            )
            products.append(product)

        # Site links + costs for promo pricing UI (same IDs as seed_promo_demo).
        site_demo = [
            {
                "granit_id": 26212,
                "wp_id": "6219",
                "site_name": "De’Longhi ECAM450.65.S Eletta Explore",
                "sku": "ECAM450.65.S",
                "regular": Decimal("3599.00"),
                "sale": Decimal("2154.00"),
                "last_cost": Decimal("1702.00"),
                "avg_cost": Decimal("1900.00"),
                "stock": Decimal("2"),
            },
            {
                "granit_id": 24313,
                "wp_id": "3621",
                "site_name": "De’Longhi Dedica EC685.M",
                "sku": "EC685.M",
                "regular": Decimal("699.00"),
                "sale": Decimal("420.00"),
                "last_cost": Decimal("280.00"),
                "avg_cost": Decimal("300.00"),
                "stock": Decimal("5"),
            },
        ]
        today = date.today()
        for item in site_demo:
            product = Product.objects.get(granit_id=item["granit_id"])
            GranitWpMapping.objects.update_or_create(
                wp_product_id=item["wp_id"],
                defaults={"granit_id": item["granit_id"]},
            )
            SiteProduct.objects.update_or_create(
                wp_product_id=item["wp_id"],
                defaults={
                    "name": item["site_name"],
                    "sku": item["sku"],
                    "url": f"https://dimkava.ge/?p={item['wp_id']}",
                    "regular_price": item["regular"],
                    "sale_price": item["sale"],
                    "in_stock": True,
                },
            )
            ProductCostSnapshot.objects.update_or_create(
                product=product,
                snapshot_date=today - timedelta(days=1),
                defaults={
                    "last_cost": item["last_cost"],
                    "avg_cost_90d": item["avg_cost"],
                    "stock_qty": item["stock"],
                },
            )
        return groups, products

    def _clients(self, rng: random.Random) -> list[Client]:
        clients = []
        for i in range(1, 51):
            client, _ = Client.objects.update_or_create(
                granit_id=10_000 + i,
                defaults={
                    "name": f"Demo Client {i:02d}",
                    "phone": f"5{rng.randint(10000000, 99999999)}",
                    "card_number": f"CARD{i:04d}",
                },
            )
            clients.append(client)
        return clients

    def _sales(
        self,
        rng: random.Random,
        today: date,
        stores: list[Store],
        products: list[Product],
        clients: list[Client],
    ) -> int:
        retail_stores = [s for s in stores if s.kind == Store.KIND_GROUP]
        horeca = next(s for s in stores if s.granit_id == 178)
        start = today - timedelta(days=90)
        line = 0
        facts: list[SaleFact] = []
        # ~400 lines across sources over 3 months.
        for day_offset in range(91):
            day = start + timedelta(days=day_offset)
            for _ in range(rng.randint(3, 6)):
                line += 1
                product = rng.choice(products)
                store = rng.choice(retail_stores)
                qty = Decimal(str(round(rng.uniform(0.25, 3.0), 3))) if product.granit_id in (101, 102) else Decimal(1)
                amount = (qty * Decimal(rng.randint(8, 120))).quantize(Decimal("0.01"))
                facts.append(
                    SaleFact(
                        sale_date=day,
                        source=SOURCE_RECEIPT,
                        store=store,
                        client=rng.choice(clients) if rng.random() < 0.7 else None,
                        product=product,
                        quantity=qty,
                        amount=amount,
                        granit_sale_id=line,
                        granit_line_id=1,
                    )
                )
            if day_offset % 7 == 0:
                line += 1
                product = rng.choice(products)
                facts.append(
                    SaleFact(
                        sale_date=day,
                        source=SOURCE_INVOICE,
                        store=horeca,
                        client=rng.choice(clients),
                        product=product,
                        quantity=Decimal("2"),
                        amount=Decimal("90.00"),
                        granit_sale_id=line,
                        granit_line_id=1,
                    )
                )
                line += 1
                facts.append(
                    SaleFact(
                        sale_date=day,
                        source=SOURCE_SERVICE,
                        store=horeca,
                        client=rng.choice(clients),
                        product=product,
                        quantity=Decimal("1"),
                        amount=Decimal("40.00"),
                        granit_sale_id=line,
                        granit_line_id=1,
                    )
                )
                line += 1
                facts.append(
                    SaleFact(
                        sale_date=day,
                        source=SOURCE_REALIZED,
                        store=horeca,
                        client=None,
                        product=product,
                        quantity=Decimal("1"),
                        amount=Decimal("55.00"),
                        granit_sale_id=line,
                        granit_line_id=1,
                    )
                )
        SaleFact.objects.bulk_create(facts, batch_size=500)
        return len(facts)

    def _stock(
        self, today: date, stores: list[Store], products: list[Product], rng: random.Random
    ) -> int:
        rows = []
        for store in stores:
            if store.kind != Store.KIND_GROUP:
                continue
            for product in products:
                rows.append(
                    StockSnapshot(
                        snapshot_date=today,
                        store=store,
                        product=product,
                        quantity=Decimal(rng.randint(0, 40)),
                    )
                )
        StockSnapshot.objects.bulk_create(rows, ignore_conflicts=True)
        return len(rows)

    def _reconcile(self, today: date, stores: list[Store]) -> int:
        """Three months: ok, open, bad — enough for badge UI."""
        month_closed = date(today.year, today.month, 1) - timedelta(days=1)
        month_closed = date(month_closed.year, month_closed.month, 1)
        month_open = date(today.year, today.month, 1)
        month_ok = (month_closed - timedelta(days=1)).replace(day=1)

        def store_row(store: Store, granit: float, ours: float, flags: list[str]) -> dict:
            return {
                "store": store.granit_id,
                "name": store.name,
                "docs": 3,
                "warehouses": [{"id": store.granit_id, "name": store.name, "amount": granit}],
                "granit_total": granit,
                "granit_goods": granit * 0.7,
                "granit_services": granit * 0.3,
                "leftover": 10.0 if "leftover" in flags else 0.0,
                "ours_goods": ours * 0.7,
                "ours_services": ours * 0.3,
                "ours_total": ours,
                "diff": ours - granit,
                "diff_goods": 0.0,
                "diff_services": 0.0,
                "flags": flags,
            }

        retail = [s for s in stores if s.kind == Store.KIND_GROUP][:3]

        def snap(month: date, state: str, bad: bool) -> None:
            rows = []
            for i, store in enumerate(retail):
                if bad and i == 0:
                    rows.append(store_row(store, 150.0, 140.0, ["leftover", "diff"]))
                else:
                    rows.append(store_row(store, 200.0, 200.0, []))
            totals = {
                "granit_total": sum(r["granit_total"] for r in rows),
                "ours_total": sum(r["ours_total"] for r in rows),
                "diff": sum(r["diff"] for r in rows),
                "leftover": sum(r["leftover"] for r in rows),
            }
            flags = []
            for r in rows:
                for kind in r["flags"]:
                    flags.append({"kind": kind, "store": r["name"], "amount": r.get(kind, r["diff"])})
            ReconcileSnapshot.objects.update_or_create(
                month=month,
                defaults={
                    "granit_total": Decimal(str(totals["granit_total"])),
                    "ours_total": Decimal(str(totals["ours_total"])),
                    "flag_count": len(flags),
                    "data": {
                        "month": month.isoformat(),
                        "state": state,
                        "stores": rows,
                        "totals": totals,
                        "services": [
                            {
                                "id": 1,
                                "name": "ремонт кофеварки",
                                "granit": 100.0,
                                "ours": 100.0,
                                "new": True,
                            }
                        ],
                        "other_types": [{"typ": 1, "docs": 4, "amount": 500.0}],
                        "flags": flags,
                    },
                },
            )

        snap(month_ok, "closed", bad=False)
        snap(month_closed, "closed", bad=True)
        snap(month_open, "open", bad=False)
        return 3

    def _campaigns(
        self,
        rng: random.Random,
        today: date,
        stores: list[Store],
        products: list[Product],
        clients: list[Client],
    ) -> int:
        sent = today - timedelta(days=20)
        date_from = sent
        date_to = sent + timedelta(days=14)

        sms = Campaign.objects.create(
            name="Demo SMS Autumn blast",
            channel=Campaign.CHANNEL_SMS,
            sms_sent_on=sent,
            notes="UI demo SMS campaign",
        )
        tg = Campaign.objects.create(
            name="Demo Telegram bot blast",
            channel=Campaign.CHANNEL_TELEGRAM,
            sms_sent_on=sent + timedelta(days=2),
            notes="UI demo Telegram campaign",
        )

        # Ensure some clients have sales in the analysis window.
        store = next(s for s in stores if s.kind == Store.KIND_GROUP)
        product = products[0]
        for client in clients[:15]:
            SaleFact.objects.create(
                sale_date=date_from + timedelta(days=rng.randint(0, 10)),
                source=SOURCE_RECEIPT,
                store=store,
                client=client,
                product=product,
                quantity=Decimal("1"),
                amount=Decimal(rng.randint(20, 80)),
                granit_sale_id=90_000 + client.granit_id,
                granit_line_id=1,
            )

        sms_rows = [
            CampaignRow(granit_client_id=c.granit_id, phone=c.phone, card_number=c.card_number)
            for c in clients[:40]
        ]
        tg_rows = [
            CampaignRow(granit_client_id=c.granit_id, phone=c.phone, card_number=c.card_number)
            for c in clients[5:45]
        ]
        analyze_rows(sms, sms_rows, date_from, date_to)
        analyze_rows(tg, tg_rows, date_from + timedelta(days=2), date_to + timedelta(days=2))
        return 2

    def _promos(
        self,
        rng: random.Random,
        today: date,
        stores: list[Store],
        products: list[Product],
        groups: list[ProductGroup],
    ) -> int:
        machine = next(p for p in products if p.granit_id == 26212)
        dedica = next(p for p in products if p.granit_id == 24313)
        coffee = next(p for p in products if p.granit_id == 101)
        store = next(s for s in stores if s.kind == Store.KIND_GROUP)

        active = Promo.objects.create(
            name="Demo AUTUMN SALE (active)",
            start_date=today - timedelta(days=7),
            end_date=today + timedelta(days=14),
            pre_period_days=14,
            promo_type="Акция / реклама",
            format="карусель предложений",
            channels="online / stores",
            notes="Active promo with analysis for charts",
        )
        PromoProduct.objects.create(promo=active, product=machine, manual_sale_price=Decimal("2154.00"))
        PromoProduct.objects.create(promo=active, product=dedica, manual_sale_price=Decimal("420.00"))

        past_start = today - timedelta(days=60)
        past_end = past_start + timedelta(days=10)
        past = Promo.objects.create(
            name="Demo SUMMER clearance (past)",
            start_date=past_start,
            end_date=past_end,
            pre_period_days=14,
            promo_type="Распродажа",
            channels="stores",
            notes="Past promo with analysis",
        )
        PromoProduct.objects.create(promo=past, product=coffee)

        bare = Promo.objects.create(
            name="Demo draft without analysis",
            start_date=today + timedelta(days=30),
            end_date=today + timedelta(days=44),
            pre_period_days=14,
            notes="No sale facts / no analysis rows",
        )
        PromoProduct.objects.create(promo=bare, product_group=groups[0])

        # Dense daily sales around active and past windows so charts have data.
        line = 200_000
        for promo, product, boost in (
            (active, machine, Decimal("180")),
            (past, coffee, Decimal("90")),
        ):
            day = promo.start_date - timedelta(days=promo.pre_period_days)
            end = promo.end_date + timedelta(days=7)
            while day <= end:
                base = boost if promo.start_date <= day <= promo.end_date else boost * Decimal("0.55")
                amount = (base + Decimal(rng.randint(-10, 20))).quantize(Decimal("0.01"))
                line += 1
                SaleFact.objects.create(
                    sale_date=day,
                    source=SOURCE_RECEIPT,
                    store=store,
                    product=product,
                    quantity=Decimal("1"),
                    amount=max(amount, Decimal("1.00")),
                    granit_sale_id=line,
                    granit_line_id=1,
                )
                day += timedelta(days=1)
            analyze_promo(promo)

        return 3
