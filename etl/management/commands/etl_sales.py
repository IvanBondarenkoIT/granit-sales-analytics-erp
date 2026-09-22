from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from etl.pipeline import default_backfill_range, finish_run, load_sales_range, start_run
from etl.proxy import ProxyApiError


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise CommandError(f"Dates must be YYYY-MM-DD, got {value!r}") from exc


class Command(BaseCommand):
    help = "Load sale facts for [from, to). Defaults to 12 months ending yesterday."

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="date_from", help="Inclusive start YYYY-MM-DD")
        parser.add_argument("--to", dest="date_to", help="Exclusive end YYYY-MM-DD")

    def handle(self, *args, **options):
        if options["date_from"] or options["date_to"]:
            if not (options["date_from"] and options["date_to"]):
                raise CommandError("Pass both --from and --to, or neither.")
            date_from = _parse_date(options["date_from"])
            date_to = _parse_date(options["date_to"])
        else:
            date_from, date_to = default_backfill_range()

        self.stdout.write(f"sales range [{date_from}, {date_to})")
        run = start_run("sales")
        try:
            stats = load_sales_range(
                date_from,
                date_to,
                progress=lambda day, count: self.stdout.write(f"  {day}: {count} lines"),
            )
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
            details={"from": str(date_from), "to": str(date_to), **stats},
        )
        self.stdout.write(self.style.SUCCESS(f"sales loaded: {stats}"))
