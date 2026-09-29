#!/usr/bin/env python
"""Verify Django migrates into schema `analytics` the way pg-core is set up on alt.

Usage:
    PG_ADMIN_URL=postgresql://postgres:postgres@localhost:5432/granit \\
      python scripts/check_pg_schema.py [--reset]

Admin phase creates role/schemas like the server (search_path = analytics, core,
no CREATE on public). App phase runs migrate as role `analytics` and checks that
django_* / dim_* / fact_* tables land in `analytics`, not public or core.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ROLE = "analytics"
ROLE_PASSWORD = "analytics"
EXPECTED_TABLES = (
    "django_migrations",
    "django_content_type",
    "auth_user",
    "dim_store",
    "dim_client",
    "dim_product",
    "dim_product_group",
    "fact_sale",
    "fact_stock_snapshot",
    "campaign",
    "campaign_client",
    "promo",
    "promo_product",
    "promo_analysis",
    "etl_run",
    "etl_watermark",
)


def _parse_admin(admin_url: str) -> tuple[str, str, str, str, str]:
    parsed = urlparse(admin_url)
    if not parsed.hostname or not parsed.path.lstrip("/"):
        raise ValueError("PG_ADMIN_URL must include host and database name")
    db = parsed.path.lstrip("/")
    user = parsed.username or "postgres"
    password = parsed.password or ""
    port = str(parsed.port or 5432)
    return parsed.hostname, port, user, password, db


def _psycopg_connect(admin_url: str):
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    host, port, user, password, db = _parse_admin(admin_url)
    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname=db,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def admin_phase(admin_url: str, reset: bool) -> dict[str, str]:
    conn = _psycopg_connect(admin_url)
    try:
        with conn.cursor() as cur:
            if reset:
                cur.execute(f"DROP SCHEMA IF EXISTS {ROLE} CASCADE")
            cur.execute(
                "DO $$ BEGIN "
                f"IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{ROLE}') THEN "
                f"CREATE ROLE {ROLE} LOGIN PASSWORD '{ROLE_PASSWORD}'; "
                "END IF; END $$"
            )
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {ROLE} AUTHORIZATION {ROLE}")
            cur.execute("CREATE SCHEMA IF NOT EXISTS core")
            # Same-named table in core must not shadow app tables.
            cur.execute("CREATE TABLE IF NOT EXISTS core.dim_store (id integer primary key)")
            cur.execute(f"GRANT USAGE ON SCHEMA core TO {ROLE}")
            cur.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA core TO {ROLE}")
            cur.execute(f"ALTER ROLE {ROLE} SET search_path = {ROLE}, core")
            cur.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
            cur.execute(f"GRANT CONNECT ON DATABASE {urlparse(admin_url).path.lstrip('/')} TO {ROLE}")
            cur.execute(f"GRANT CREATE ON SCHEMA {ROLE} TO {ROLE}")
    finally:
        conn.close()

    host, port, _, _, db = _parse_admin(admin_url)
    return {
        "DB_HOST": host,
        "DB_PORT": port,
        "DB_NAME": db,
        "DB_USER": ROLE,
        "DB_PASSWORD": ROLE_PASSWORD,
        "DB_SSLMODE": "disable",
    }


def report_failure(message: str) -> None:
    print(f"FAIL: {message}")
    if os.environ.get("GITHUB_ACTIONS"):
        flat = message.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
        print(f"::error title=check_pg_schema::{flat}")


def app_phase() -> int:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "granitanalytics.settings")
    import django
    from django.core.management import call_command
    from django.db import connection

    django.setup()
    call_command("migrate", "--noinput", verbosity=1)

    problems: list[str] = []
    with connection.cursor() as cur:
        cur.execute("SELECT current_schema()")
        current = cur.fetchone()[0]
        if current != ROLE:
            problems.append(f"current_schema() = {current!r}, expected {ROLE!r}")

        cur.execute(
            "SELECT schemaname, tablename FROM pg_tables WHERE tablename = ANY(%s)",
            [list(EXPECTED_TABLES)],
        )
        rows = cur.fetchall()
        in_analytics = {t for s, t in rows if s == ROLE}
        missing = sorted(set(EXPECTED_TABLES) - in_analytics)
        if missing:
            problems.append(f"tables missing in {ROLE}: {missing}")
        in_public = sorted(t for s, t in rows if s == "public")
        if in_public:
            problems.append(f"tables created in public: {in_public}")
        shadowed = sorted(
            t for s, t in rows if s == "core" and t in EXPECTED_TABLES and t not in in_analytics
        )
        if shadowed:
            problems.append(f"expected tables only in core (not analytics): {shadowed}")

    if problems:
        for p in problems:
            report_failure(p)
        return 1
    print(f"OK: {len(EXPECTED_TABLES)} expected tables present in schema {ROLE}")
    return 0


def run_guarded(fn, *args) -> int:
    try:
        return fn(*args)
    except Exception as exc:  # noqa: BLE001
        report_failure(f"{type(exc).__name__}: {exc}"[:1500])
        return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Check Django schema placement on Postgres")
    parser.add_argument("--reset", action="store_true", help="drop schema analytics first")
    parser.add_argument("--app-phase", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.app_phase:
        return run_guarded(app_phase)

    admin_url = (os.environ.get("PG_ADMIN_URL") or "").strip()
    if not admin_url:
        print("PG_ADMIN_URL is not set", file=sys.stderr)
        return 2
    try:
        db_env = admin_phase(admin_url, args.reset)
    except Exception as exc:  # noqa: BLE001
        report_failure(f"admin phase: {type(exc).__name__}: {exc}"[:1500])
        return 1

    env = {k: v for k, v in os.environ.items() if not k.startswith("PG_")}
    env.update(db_env)
    env["SECRET_KEY"] = "check-pg-schema-secret-not-for-prod"
    env["DEBUG"] = "False"
    env["ALLOWED_HOSTS"] = "localhost"
    env.pop("DB_SEARCH_PATH", None)
    return subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--app-phase"],
        cwd=str(ROOT),
        env=env,
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
