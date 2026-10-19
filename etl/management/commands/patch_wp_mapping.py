"""Update one granit_id → wp-id in Google Sheets and reload GranitWpMapping."""
from django.core.management.base import BaseCommand, CommandError

from etl.pipeline import finish_run, load_wp_mapping, start_run
from etl.sheets import (
    parse_granit_sheet_rows,
    set_granit_sheet_wp_id,
    sheets_configured,
)


def _read_mapping_rows(*, insecure_ssl: bool = False) -> list[dict[str, str]]:
    from etl.sheets import _open_granit_worksheet

    # Write scope also allows read; use it when insecure so one session works.
    ws = _open_granit_worksheet(readonly=not insecure_ssl, insecure_ssl=insecure_ssl)
    values = ws.get_all_values()
    if not values:
        return []
    headers = [str(h).strip() for h in values[0]]
    rows: list[dict[str, str]] = []
    for line in values[1:]:
        if not any(str(c).strip() for c in line):
            continue
        row = {}
        for i, header in enumerate(headers):
            if not header:
                continue
            row[header] = str(line[i] if i < len(line) else "").strip()
        rows.append(row)
    return rows


class Command(BaseCommand):
    help = (
        "Set wp-id for a granit_id in the Google Sheets granit tab, then reload "
        "GranitWpMapping into the database."
    )

    def add_arguments(self, parser):
        parser.add_argument("--granit-id", type=int, required=True)
        parser.add_argument("--wp-id", required=True, help="WooCommerce product id")
        parser.add_argument(
            "--db-only",
            action="store_true",
            help="Skip Sheets write; only upsert this pair in DB (not replaced by full reload).",
        )
        parser.add_argument(
            "--insecure-ssl",
            action="store_true",
            help="Disable SSL verify for Google APIs (corporate MITM / broken CA chain).",
        )
        parser.add_argument(
            "--skip-reload",
            action="store_true",
            help="Update Sheets only; do not replace GranitWpMapping from the full sheet.",
        )

    def handle(self, *args, **options):
        granit_id = int(options["granit_id"])
        wp_id = str(options["wp_id"]).strip()
        if not wp_id:
            raise CommandError("--wp-id is empty")

        if options["db_only"]:
            from core.models import GranitWpMapping

            GranitWpMapping.objects.filter(granit_id=granit_id).exclude(
                wp_product_id=wp_id
            ).delete()
            GranitWpMapping.objects.update_or_create(
                wp_product_id=wp_id,
                defaults={"granit_id": granit_id},
            )
            self.stdout.write(
                self.style.SUCCESS(f"db-only: granit {granit_id} → wp {wp_id}")
            )
            return

        if not sheets_configured():
            raise CommandError("Sheets not configured")

        insecure = bool(options["insecure_ssl"])
        try:
            sheet_stats = set_granit_sheet_wp_id(
                granit_id, wp_id, insecure_ssl=insecure
            )
        except Exception as exc:
            raise CommandError(f"Sheets update failed: {exc}") from exc
        self.stdout.write(f"sheet: {sheet_stats}")

        if options["skip_reload"]:
            self.stdout.write(self.style.SUCCESS("Sheets updated; reload skipped"))
            return

        run = start_run("wp_mapping")
        try:
            if insecure:
                pairs = parse_granit_sheet_rows(_read_mapping_rows(insecure_ssl=True))
                stats = load_wp_mapping(pairs=pairs)
            else:
                stats = load_wp_mapping()
        except Exception as exc:
            finish_run(run, error=str(exc))
            raise CommandError(str(exc)) from exc
        finish_run(run, inserted=stats.get("rows", 0), processed=stats.get("rows", 0), details=stats)
        self.stdout.write(self.style.SUCCESS(f"wp mapping reloaded: {stats}"))
