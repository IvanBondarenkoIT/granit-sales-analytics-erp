"""One-off Excel: Blaser pack buyers at ~10% off for a date window."""
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from sales.blaser_cert import build_report, write_report_xlsx


def _parse_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise CommandError(f"Dates must be YYYY-MM-DD, got {value!r}") from exc


class Command(BaseCommand):
    help = (
        "Find retail clients who bought Blaser 1kg/250g packs at ~10% off "
        "(certificate proxy). Writes Excel under data/local/ by default."
    )

    def add_arguments(self, parser):
        parser.add_argument("--from", dest="date_from", default="2025-10-15")
        parser.add_argument(
            "--to",
            dest="date_to",
            default="2026-10-16",
            help="Exclusive end date (default day after 2026-10-15)",
        )
        parser.add_argument(
            "--out",
            dest="out_path",
            default="",
            help="Output .xlsx path (default data/local/blaser_cert_<from>_<to>.xlsx)",
        )

    def handle(self, *args, **options):
        date_from = _parse_date(options["date_from"])
        date_to = _parse_date(options["date_to"])
        if date_to <= date_from:
            raise CommandError("--to must be after --from")

        out = options["out_path"]
        if not out:
            out = (
                Path(settings.BASE_DIR)
                / "data"
                / "local"
                / f"blaser_cert_{date_from.isoformat()}_{date_to.isoformat()}.xlsx"
            )
        else:
            out = Path(out)

        self.stdout.write(f"Blaser −10% window [{date_from}, {date_to})")
        report = build_report(date_from, date_to)
        path = write_report_xlsx(report, out)
        s = report.summary
        self.stdout.write(
            f"promo clients: {s['promo_clients']} "
            f"(once {s['visits_once_pct']}%, multi {s['visits_multi_pct']}%)"
        )
        self.stdout.write(
            f"contacts: phone {s['with_phone']}, card {s['with_card']}, either {s['with_contact']}"
        )
        self.stdout.write(
            f"lines: full {s['blaser_lines_full']}, "
            f"promo_10 {s['blaser_lines_promo_10']}, other {s['blaser_lines_other']}"
        )
        self.stdout.write(
            f"machine buyers in window: {s['machine_buyers_in_window']}, "
            f"used promo: {s['machine_buyers_used_promo']} ({s['machine_buyers_used_promo_pct']}%)"
        )
        self.stdout.write(f"loyalty card lines (24303): {s['loyalty_card_lines']}")
        self.stdout.write(self.style.SUCCESS(f"wrote {path}"))
