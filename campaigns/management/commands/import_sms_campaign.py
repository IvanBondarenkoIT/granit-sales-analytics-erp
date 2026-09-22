from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from campaigns.analysis import DEFAULT_SMS_SENT_ON, LOCAL_SMS_XLSX, import_campaign_from_path


class Command(BaseCommand):
    help = "Import local SMS Excel and score bought / not bought for a period."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(LOCAL_SMS_XLSX))
        parser.add_argument("--name", default="SMS 18 Sep 2026")
        parser.add_argument("--from", dest="date_from", default=DEFAULT_SMS_SENT_ON.isoformat())
        parser.add_argument("--to", dest="date_to", default=date.today().isoformat())

    def handle(self, *args, **options):
        try:
            date_from = datetime.strptime(options["date_from"], "%Y-%m-%d").date()
            date_to = datetime.strptime(options["date_to"], "%Y-%m-%d").date()
            campaign = import_campaign_from_path(
                options["file"],
                name=options["name"],
                date_from=date_from,
                date_to=date_to,
                notes=f"SMS sent on {DEFAULT_SMS_SENT_ON.isoformat()}",
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"campaign #{campaign.pk}: {campaign.clients_with_sales}/{campaign.total_clients} bought "
                f"[{date_from}, {date_to})"
            )
        )
