from datetime import date

from django.core.management.base import BaseCommand, CommandError

from etl.proxy import ProxyApiError
from etl.reconcile import month_start, refresh_months


class Command(BaseCommand):
    help = "Reconcile our sales with Granit sales documents per store and month; exit 1 when there are flags."

    def add_arguments(self, parser):
        parser.add_argument("--month", help="YYYY-MM (default: current month)")
        parser.add_argument("--months", type=int, default=1, help="How many months back from --month")

    def handle(self, *args, **options):
        if options["month"]:
            try:
                last = date.fromisoformat(f"{options['month']}-01")
            except ValueError as exc:
                raise CommandError("--month must be YYYY-MM") from exc
        else:
            last = month_start(date.today())
        try:
            snapshots = refresh_months(last, max(1, options["months"]))
        except ProxyApiError as exc:
            raise CommandError(str(exc)) from exc

        flagged = 0
        for snap in sorted(snapshots, key=lambda s: s.month):
            data = snap.data
            state = data.get("state", "closed")
            self.stdout.write(
                f"{snap.month:%Y-%m}: granit {snap.granit_total} / ours {snap.ours_total} / diff {snap.diff:.2f}"
                f" / services {data['totals']['granit_services']:.2f} / leftover {data['totals']['leftover']:.2f}"
                + ("" if state == "closed" else f" [{state}, not flagged]")
            )
            for flag in data["flags"]:
                self.stdout.write(f"    {flag['kind']}: {flag['store']} {flag['amount']:.2f}")
            flagged += snap.flag_count
        if flagged:
            raise CommandError(f"{flagged} reconciliation flag(s)")
        self.stdout.write(self.style.SUCCESS("Reconciliation OK"))
