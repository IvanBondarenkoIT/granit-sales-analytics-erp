"""Seed a few site↔granit links and cost rows for local promo UI demos."""
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import GranitWpMapping, Product, ProductCostSnapshot, SiteProduct
from promos.models import Promo, PromoProduct


class Command(BaseCommand):
    help = "Seed demo SiteProduct / mapping / costs for local promo control UI."

    def handle(self, *args, **options):
        today = date.today()
        demo = [
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
        linked = 0
        for item in demo:
            product = Product.objects.filter(granit_id=item["granit_id"]).first()
            if product is None:
                product = Product.objects.create(
                    granit_id=item["granit_id"],
                    name=item["site_name"],
                    is_active=True,
                )
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
            linked += 1

        promo, created = Promo.objects.get_or_create(
            name="Demo AUTUMN SALE (seed)",
            defaults={
                "start_date": today - timedelta(days=7),
                "end_date": today + timedelta(days=14),
                "pre_period_days": 14,
                "promo_type": "Акция / реклама",
                "format": "карусель предложений",
                "channels": "online / stores",
                "notes": "Local seed for promo control prices UI",
            },
        )
        if created or not promo.promo_products.exists():
            for item in demo:
                product = Product.objects.get(granit_id=item["granit_id"])
                PromoProduct.objects.get_or_create(promo=promo, product=product)

        self.stdout.write(
            self.style.SUCCESS(
                f"seeded {linked} site SKUs; promo id={promo.pk} created={created} at {timezone.now()}"
            )
        )
