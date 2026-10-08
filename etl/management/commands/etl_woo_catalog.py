from django.core.management.base import BaseCommand, CommandError

from etl.pipeline import finish_run, load_woo_catalog, start_run
from etl.woo import woo_configured


class Command(BaseCommand):
    help = "Sync WooCommerce catalog into SiteProduct."

    def handle(self, *args, **options):
        if not woo_configured():
            self.stdout.write(self.style.WARNING("Woo API not configured — skipped."))
            return
        run = start_run("woo_catalog")
        try:
            stats = load_woo_catalog()
        except Exception as exc:
            finish_run(run, error=str(exc))
            raise CommandError(str(exc)) from exc
        finish_run(run, inserted=stats.get("rows", 0), processed=stats.get("rows", 0), details=stats)
        self.stdout.write(self.style.SUCCESS(f"woo catalog: {stats}"))
