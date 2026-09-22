from django.core.management.base import BaseCommand, CommandError

from etl.proxy import ProxyApiError, health_check


class Command(BaseCommand):
    help = "Ping firebird-db-proxy GET /api/health (does not print secrets)."

    def handle(self, *args, **options):
        try:
            payload = health_check()
        except ProxyApiError as exc:
            raise CommandError(str(exc)) from exc
        status = payload.get("status") or payload.get("ok") or payload.get("success") or "ok"
        self.stdout.write(self.style.SUCCESS(f"proxy health: {status}"))
