# Super-group seed

`supergroups.json` is copied from `monthly-sales-report/mapping/supergroups.yaml`
(July 2026 drinks split). Excel sample files stay in the parent repo and are not
committed here.

## How groups become super-groups

Resolve order for each Granit `GOODSGROUPS` row:

1. Exact `group_id` in `rules.by_group_id`.
2. Longest matching `parent_path` prefix in `rules.by_parent_path_prefix`
   (path is built from names via `PARENTID`, e.g. `DRINKS > Water`).
3. Optional ancestor id (empty in the default seed).
4. Otherwise the group stays **outside** super-groups (no membership row).

Keys `unclassified` and `exclude` from the parent YAML are **not** created as
editable super-groups. Sales for those groups (and for products with no group)
appear in the synthetic catch-all row **Outside super-groups**, so store and
period totals still match `SaleFact`.

## Commands

```bash
python manage.py seed_supergroups          # only if SuperGroup table is empty
python manage.py seed_supergroups --fill-unmapped   # map groups still without a member
```

Production (container `granit-analytics`):

```bash
docker exec granit-analytics python manage.py etl_dims
docker exec granit-analytics python manage.py seed_supergroups
```

Edits in the UI are shared for all users and are not overwritten by a plain seed.
