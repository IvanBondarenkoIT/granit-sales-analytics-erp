from datetime import date

from django.core.management.base import BaseCommand, CommandError

from etl.models import ETLRun
from etl.pipeline import CATALOG_RUN_TYPE, catalog_sync_running, run_catalog_sync


class Command(BaseCommand):
    help = (
        "Catalog sync: Granit products/groups + Sheets wp-id mapping + "
        "Woo categories/products + Granit costs and stock."
    )

    def add_arguments(self, parser):
        parser.add_argument("--no-dims", action="store_true", help="Skip Granit products/groups reload")
        parser.add_argument("--date", type=date.fromisoformat, help="Cost snapshot date (default yesterday)")
        parser.add_argument("--force", action="store_true", help="Run even if another sync looks active")
        parser.add_argument("--run-id", type=int, help="Continue an ETLRun created by the web UI")

    def handle(self, *args, **options):
        run = None
        if options.get("run_id"):
            run = ETLRun.objects.filter(
                pk=options["run_id"], etl_type=CATALOG_RUN_TYPE, status="running"
            ).first()
            if run is None:
                raise CommandError(f"No running catalog ETLRun #{options['run_id']}.")
        elif not options["force"] and catalog_sync_running():
            raise CommandError("Another catalog sync is running; use --force to override.")
        details = run_catalog_sync(
            include_dims=not options["no_dims"],
            snapshot_date=options.get("date"),
            run=run,
        )
        self.stdout.write(self.style.SUCCESS(f"catalog sync: {details}"))
