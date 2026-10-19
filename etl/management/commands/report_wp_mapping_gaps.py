"""List Sheets mappings without Woo products and Woo products without mapping."""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from etl.wp_mapping_report import build_mapping_gaps_report, write_mapping_gaps_xlsx


class Command(BaseCommand):
    help = (
        "Report Granit↔Woo gaps: mapping rows whose wp-id is missing in SiteProduct, "
        "and SiteProducts with no GranitWpMapping. Writes Excel under data/local/."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            dest="out_path",
            default="",
            help="Output .xlsx path (default data/local/wp_mapping_gaps.xlsx)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="How many sample rows to print per list (default 20)",
        )

    def handle(self, *args, **options):
        report = build_mapping_gaps_report()
        out = options["out_path"]
        if not out:
            out = Path(settings.BASE_DIR) / "data" / "local" / "wp_mapping_gaps.xlsx"
        else:
            out = Path(out)
        path = write_mapping_gaps_xlsx(report, out)
        limit = max(0, int(options["limit"]))

        self.stdout.write(
            f"mapping without SiteProduct: {len(report.mapping_without_site)}"
        )
        for row in report.mapping_without_site[:limit]:
            self.stdout.write(
                f"  wp={row.wp_product_id} granit={row.granit_id} {row.granit_name}"
            )
        if len(report.mapping_without_site) > limit:
            self.stdout.write(f"  … +{len(report.mapping_without_site) - limit} more")

        self.stdout.write(
            f"SiteProduct without mapping: {len(report.site_without_mapping)}"
        )
        for row in report.site_without_mapping[:limit]:
            sku = f" sku={row.sku}" if row.sku else ""
            self.stdout.write(f"  wp={row.wp_product_id}{sku} {row.site_name}")
        if len(report.site_without_mapping) > limit:
            self.stdout.write(f"  … +{len(report.site_without_mapping) - limit} more")

        self.stdout.write(self.style.SUCCESS(f"wrote {path}"))
