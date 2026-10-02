from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from etl.pipeline import (
    finish_run,
    load_dims,
    load_sales_range,
    load_stock,
    nightly_reload_range,
    start_run,
)
from etl.proxy import ProxyApiError


class Command(BaseCommand):
    help = "Nightly ETL: dims + sales reload window (ETL_RELOAD_MONTHS) + stock snapshot."

    def handle(self, *args, **options):
        yesterday = date.today() - timedelta(days=1)
        sales_from, sales_to = nightly_reload_range()
        run = start_run("incremental")
        details = {
            "date": str(yesterday),
            "sales_from": str(sales_from),
            "sales_to": str(sales_to - timedelta(days=1)),
        }
        try:
            details["dims"] = load_dims()
            details["sales"] = load_sales_range(sales_from, sales_to)
            details["stock"] = load_stock(yesterday)
        except ProxyApiError as exc:
            finish_run(run, error=str(exc), details=details)
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            finish_run(run, error=str(exc), details=details)
            raise
        rows = details["sales"].get("rows", 0) + details["stock"].get("rows", 0)
        finish_run(run, inserted=rows, processed=rows, details=details)
        self.stdout.write(
            self.style.SUCCESS(f"nightly {yesterday} (sales {sales_from}..{yesterday}): {details}")
        )
