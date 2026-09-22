from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from etl.pipeline import finish_run, load_dims, load_sales_range, load_stock, start_run
from etl.proxy import ProxyApiError


class Command(BaseCommand):
    help = "Nightly ETL: dims + yesterday sales + stock snapshot."

    def handle(self, *args, **options):
        yesterday = date.today() - timedelta(days=1)
        run = start_run("incremental")
        details = {"date": str(yesterday)}
        try:
            details["dims"] = load_dims()
            details["sales"] = load_sales_range(yesterday, yesterday + timedelta(days=1))
            details["stock"] = load_stock(yesterday)
        except ProxyApiError as exc:
            finish_run(run, error=str(exc), details=details)
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            finish_run(run, error=str(exc), details=details)
            raise
        rows = details["sales"].get("rows", 0) + details["stock"].get("rows", 0)
        finish_run(run, inserted=rows, processed=rows, details=details)
        self.stdout.write(self.style.SUCCESS(f"nightly {yesterday}: {details}"))
