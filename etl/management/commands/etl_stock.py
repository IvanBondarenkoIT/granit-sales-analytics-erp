from datetime import date, datetime, timedelta

from django.core.management.base import BaseCommand, CommandError

from etl.pipeline import finish_run, load_stock, start_run
from etl.proxy import ProxyApiError


class Command(BaseCommand):
    help = "Load yesterday company-ledger stock snapshot for known SKUs."

    def add_arguments(self, parser):
        parser.add_argument("--date", dest="snapshot_date", help="Snapshot date YYYY-MM-DD (default: yesterday)")

    def handle(self, *args, **options):
        if options["snapshot_date"]:
            try:
                snapshot = datetime.strptime(options["snapshot_date"], "%Y-%m-%d").date()
            except ValueError as exc:
                raise CommandError("Date must be YYYY-MM-DD") from exc
        else:
            snapshot = date.today() - timedelta(days=1)

        run = start_run("stock")
        try:
            stats = load_stock(snapshot)
        except ProxyApiError as exc:
            finish_run(run, error=str(exc))
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            finish_run(run, error=str(exc))
            raise
        finish_run(
            run,
            inserted=stats["rows"],
            processed=stats["rows"],
            details={"date": str(snapshot), **stats},
        )
        self.stdout.write(self.style.SUCCESS(f"stock {snapshot}: {stats}"))
