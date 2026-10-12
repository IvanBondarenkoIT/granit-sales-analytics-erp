from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from etl.pipeline import (
    finish_run,
    load_dims,
    load_sales_range,
    load_stock,
    nightly_reload_range,
    run_catalog_sync,
    start_run,
)
from etl.proxy import ProxyApiError
from etl.reconcile import refresh_months


class Command(BaseCommand):
    help = (
        "Nightly ETL: dims + sales reload window + stock + "
        "optional WP mapping / Woo catalog + product costs."
    )

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

        try:
            details["reconcile"] = [
                {"month": s.month.isoformat(), "diff": float(s.diff), "flags": s.flag_count}
                for s in refresh_months(yesterday, 2)
            ]
        except Exception as exc:
            details["reconcile"] = {"error": str(exc)}
        rows = details["sales"].get("rows", 0) + details["stock"].get("rows", 0)
        finish_run(run, inserted=rows, processed=rows, details=details)
        reconcile = details["reconcile"]
        if isinstance(reconcile, dict):
            self.stderr.write(self.style.WARNING(f"reconcile failed: {reconcile['error']}"))
        else:
            for item in reconcile:
                if item["flags"]:
                    self.stderr.write(
                        self.style.WARNING(
                            f"reconcile {item['month'][:7]}: {item['flags']} flag(s), diff {item['diff']:.2f}"
                        )
                    )

        catalog = run_catalog_sync(snapshot_date=yesterday)
        details["catalog"] = catalog
        for key in ("wp_mapping", "woo_catalog", "product_costs"):
            step = catalog.get(key)
            if isinstance(step, dict) and "error" in step:
                self.stderr.write(self.style.WARNING(f"{key} failed: {step['error']}"))
        self.stdout.write(
            self.style.SUCCESS(f"nightly {yesterday} (sales {sales_from}..{yesterday}): {details}")
        )
