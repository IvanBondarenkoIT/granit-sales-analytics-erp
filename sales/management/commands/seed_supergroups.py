from django.core.management.base import BaseCommand, CommandError

from core.models import ProductGroup
from sales.models import SuperGroup, SuperGroupMember
from sales.supergroups import (
    SKIP_MEMBERSHIP_KEYS,
    build_parent_path,
    load_seed_config,
    resolve_supergroup_key,
)


def _refresh_parent_paths() -> dict[int, str]:
    groups = list(ProductGroup.objects.all())
    names = {g.granit_id: g.name for g in groups}
    parents = {g.granit_id: (g.parent.granit_id if g.parent_id else None) for g in groups}
    by_id = {g.granit_id: g for g in groups}
    paths: dict[int, str] = {}
    for g in groups:
        path = build_parent_path(g.granit_id, names, parents)
        paths[g.granit_id] = path
        if g.parent_path != path:
            g.parent_path = path
            g.save(update_fields=["parent_path", "updated_at"])
    return paths


def ensure_catalog(*, fill_unmapped: bool = False) -> dict[str, int]:
    cfg = load_seed_config()
    has_rows = SuperGroup.objects.exists()
    if has_rows and not fill_unmapped:
        return {"skipped": 1, "created_sg": 0, "members": 0}

    created_sg = 0
    by_key: dict[str, SuperGroup] = {}
    for item in cfg.catalog:
        key = str(item["key"])
        if key in SKIP_MEMBERSHIP_KEYS:
            continue
        sg, created = SuperGroup.objects.update_or_create(
            key=key,
            defaults={
                "title": str(item.get("title") or key),
                "color": str(item.get("color") or "FFFFFF").lstrip("#")[:6],
                "sort_order": int(item.get("sort_order") or 0),
                "is_catchall": False,
            },
        )
        by_key[key] = sg
        if created:
            created_sg += 1

    catchall, created_catch = SuperGroup.objects.update_or_create(
        key=cfg.catchall_key,
        defaults={
            "title": cfg.catchall_title,
            "color": cfg.catchall_color[:6],
            "sort_order": 10_000,
            "is_catchall": True,
        },
    )
    by_key[cfg.catchall_key] = catchall
    if created_catch:
        created_sg += 1

    paths = _refresh_parent_paths()
    parents = {
        g.granit_id: (g.parent.granit_id if g.parent_id else None)
        for g in ProductGroup.objects.select_related("parent")
    }
    members = 0
    for group in ProductGroup.objects.all():
        if fill_unmapped and SuperGroupMember.objects.filter(product_group=group).exists():
            continue
        if not fill_unmapped and has_rows:
            continue
        if SuperGroupMember.objects.filter(product_group=group).exists():
            continue
        key = resolve_supergroup_key(
            group.granit_id,
            paths.get(group.granit_id) or group.parent_path,
            parents=parents,
            config=cfg,
        )
        if key in SKIP_MEMBERSHIP_KEYS or key not in by_key or by_key[key].is_catchall:
            continue
        SuperGroupMember.objects.create(super_group=by_key[key], product_group=group)
        members += 1

    return {"skipped": 0, "created_sg": created_sg, "members": members}


class Command(BaseCommand):
    help = "Seed shared SuperGroup catalog from sales/seed/supergroups.json"

    def add_arguments(self, parser):
        parser.add_argument(
            "--fill-unmapped",
            action="store_true",
            help="Only assign ProductGroups that still have no membership; keep manual edits",
        )
        parser.add_argument(
            "--force-empty-only",
            action="store_true",
            help="Refuse to run unless SuperGroup table is empty (default without --fill-unmapped)",
        )

    def handle(self, *args, **options):
        fill = options["fill_unmapped"]
        if not fill and SuperGroup.objects.exists():
            raise CommandError(
                "SuperGroup table is not empty. Use --fill-unmapped to map only groups without a member."
            )
        stats = ensure_catalog(fill_unmapped=fill)
        self.stdout.write(self.style.SUCCESS(f"seed_supergroups: {stats}"))
