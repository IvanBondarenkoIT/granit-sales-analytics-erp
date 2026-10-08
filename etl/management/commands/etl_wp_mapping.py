from django.core.management.base import BaseCommand, CommandError

from etl.pipeline import finish_run, load_wp_mapping, start_run
from etl.sheets import sheets_configured


class Command(BaseCommand):
    help = "Sync Granit ↔ Woo mapping from Google Sheets (tab granit)."

    def handle(self, *args, **options):
        if not sheets_configured():
            self.stdout.write(self.style.WARNING("Sheets not configured — skipped."))
            return
        run = start_run("wp_mapping")
        try:
            stats = load_wp_mapping()
        except Exception as exc:
            finish_run(run, error=str(exc))
            raise CommandError(str(exc)) from exc
        finish_run(run, inserted=stats.get("rows", 0), processed=stats.get("rows", 0), details=stats)
        self.stdout.write(self.style.SUCCESS(f"wp mapping: {stats}"))
