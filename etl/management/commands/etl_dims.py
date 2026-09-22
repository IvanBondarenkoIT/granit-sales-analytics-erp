from django.core.management.base import BaseCommand, CommandError

from etl.pipeline import finish_run, load_dims, start_run
from etl.proxy import ProxyApiError


class Command(BaseCommand):
    help = "Load stores, groups, products, param «продукция», clients from proxy."

    def handle(self, *args, **options):
        run = start_run("dimensions")
        try:
            stats = load_dims()
        except ProxyApiError as exc:
            finish_run(run, error=str(exc))
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            finish_run(run, error=str(exc))
            raise
        processed = sum(stats.values())
        finish_run(
            run,
            inserted=stats.get("products_inserted", 0) + stats.get("clients_inserted", 0),
            updated=stats.get("products_updated", 0) + stats.get("clients_updated", 0),
            processed=processed,
            details=stats,
        )
        self.stdout.write(self.style.SUCCESS(f"dims loaded: {stats}"))
