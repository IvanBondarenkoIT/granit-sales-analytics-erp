from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from campaigns.analysis import LOCAL_SMS_XLSX, import_campaign_from_path


class Command(BaseCommand):
    help = "Create a NEW campaign from Excel. Never overwrites an existing blast."

    def add_arguments(self, parser):
        parser.add_argument("--file", default=str(LOCAL_SMS_XLSX))
        parser.add_argument("--name", required=True, help="Unique label for this blast")
        parser.add_argument("--sent-on", dest="sent_on", required=True, help="SMS send date YYYY-MM-DD")
        parser.add_argument("--to", dest="date_to", default=date.today().isoformat())

    def handle(self, *args, **options):
        try:
            sent = datetime.strptime(options["sent_on"], "%Y-%m-%d").date()
            date_to = datetime.strptime(options["date_to"], "%Y-%m-%d").date()
            campaign = import_campaign_from_path(
                options["file"],
                name=options["name"],
                date_from=sent,
                date_to=date_to,
                sms_sent_on=sent,
                notes=f"SMS sent on {sent.isoformat()}",
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                f"new campaign #{campaign.pk} {campaign.name}: "
                f"{campaign.clients_with_sales}/{campaign.total_clients} bought "
                f"sent {sent} window [{sent}, {date_to})"
            )
        )
