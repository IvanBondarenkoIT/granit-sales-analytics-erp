from datetime import date, datetime

from django.core.management.base import BaseCommand, CommandError

from campaigns.analysis import import_tg_campaign_from_path


class Command(BaseCommand):
    help = "Create a NEW Telegram-bot campaign from CSV (card,phone). Never overwrites an existing blast."

    def add_arguments(self, parser):
        parser.add_argument("--file", required=True, help="CSV path, e.g. data/local/users.csv")
        parser.add_argument("--name", required=True, help="Unique label for this blast")
        parser.add_argument("--sent-on", dest="sent_on", required=True, help="Send date YYYY-MM-DD")
        parser.add_argument("--to", dest="date_to", default=date.today().isoformat())
        parser.add_argument("--notes", default="")

    def handle(self, *args, **options):
        try:
            sent = datetime.strptime(options["sent_on"], "%Y-%m-%d").date()
            date_to = datetime.strptime(options["date_to"], "%Y-%m-%d").date()
            if date_to <= sent:
                raise ValueError("--to must be after --sent-on")
            campaign = import_tg_campaign_from_path(
                options["file"],
                name=options["name"],
                sent_on=sent,
                date_to=date_to,
                notes=options["notes"] or f"Telegram bot blast sent on {sent.isoformat()}",
            )
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        unmatched = campaign.campaign_clients.filter(client__isnull=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"new TG campaign #{campaign.pk} {campaign.name}: "
                f"{campaign.clients_with_sales}/{campaign.total_clients} bought, "
                f"{unmatched} not matched, window [{sent}, {date_to})"
            )
        )
