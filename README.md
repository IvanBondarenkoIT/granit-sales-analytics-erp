# Granit Sales Analytics ERP

Lightweight decision ERP for Granit retail chain: SMS campaign lift analysis, sales explorer, and promotion effectiveness tracking.

## Architecture Overview

This project follows a hybrid deployment architecture (see [PLAN.md](./PLAN.md) for full details):

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **PostgreSQL `pg-core`** | **alt Debian** (Docker `pgnet`) | Shared DB `granit`; this app uses schema `analytics` |
| **Nightly ETL** | **alt** (`docker exec … etl_nightly`) | Pulls from firebird-db-proxy into schema `analytics` |
| **Django + HTMX UI** | **alt** container `granit-analytics` | `analytics.dimkava.ge` via Caddy `edge` |
| **firebird-db-proxy** | Windows at Granit | Read-only API to Granit ERP (external, not modified) |

### Technology Stack

- **Backend:** Python + Django 4.2+
- **Frontend:** HTMX (lightweight, server-rendered)
- **Database:** PostgreSQL 16 (`pg-core` in production; Compose Postgres 15 locally)
- **Deployment:** Docker Compose locally; GHCR image + deploy hub on alt
- **ETL:** Django management commands in this repo (stage 1)

### Data Model

**Facts:**
- Sales transactions (date, store, client, product, quantity, amount)
- Daily stock snapshots (active SKU by store)

**Dimensions:**
- Products (SKU with group and parameter associations)
- Product Groups
- Product Parameters (e.g., "продукция" id=2)
- Stores (Granit locations)
- Clients (customer records with phone)

Only active SKU with sales or stock are tracked (no dead inventory).

## Project Structure

```
├── granitanalytics/       # Django project settings
├── core/                  # Core models: dimensions (Store, Client, Product, etc.)
├── sales/                 # Sales facts and stock snapshots
├── etl/                   # ETL run tracking and watermarks
├── campaigns/             # SMS campaign tracking and analysis
├── promos/                # Promotion effectiveness analysis
├── deploy/                # Production Compose for alt (no local Postgres)
├── scripts/               # Schema check for pg-core / analytics
├── .github/workflows/     # CI/CD → GHCR
├── docker-compose.yml     # Local development environment
├── Dockerfile             # Application container definition
├── entrypoint.sh          # migrate + compilemessages + gunicorn
├── requirements.txt       # Python dependencies
├── .env.example           # Environment variable template
├── PLAN.md                # Full architecture and implementation plan
└── CURSOR-PROMPT.md       # Development guidelines
```

## Local Development Setup

### Prerequisites

- Docker and Docker Compose
- Git

### Getting Started

1. **Clone the repository:**

```bash
git clone https://github.com/IvanBondarenkoIT/granit-sales-analytics-erp.git
cd granit-sales-analytics-erp
```

2. **Copy environment template and set secrets:**

```bash
cp .env.example .env
```

Edit `.env` and replace placeholders with your own values. At minimum set:

- `SECRET_KEY` — generate a Django secret key locally
- `DB_PASSWORD` — any local-only password
- `DB_USER` / `DB_NAME` — must match what Compose passes to Postgres

Do not commit `.env`. Compose reads variables from `.env` only (no password fallbacks in `docker-compose.yml`).

3. **Start the application:**

```bash
docker compose up
```

This will:
- Start PostgreSQL database on port 5432
- Start Django development server on port 8000
- Apply database migrations automatically

4. **Create a user (required — UI is behind login):**

```bash
docker compose exec web python manage.py createsuperuser
```

5. **Access the application:**

- Web UI: http://localhost:8000 — redirects to `/accounts/login/` until you sign in
- Register: http://localhost:8000/accounts/register/ (controlled by `ALLOW_REGISTRATION`, default on)
- Django Admin: http://localhost:8000/admin (staff/superuser)

### Translations (i18n)

- Languages: `ru` (default), `en`
- Catalogs: `locale/ru/LC_MESSAGES/`, `locale/en/LC_MESSAGES/`
- After editing `.po` files:

```bash
docker compose exec web python manage.py compilemessages
```

### Development Commands

```bash
# View logs
docker compose logs -f web

# Run migrations
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate

# Stage 2 ETL (needs PROXY_API_URL + PROXY_API_TOKEN in .env)
docker compose exec web python manage.py etl_health
docker compose exec web python manage.py etl_dims
docker compose exec web python manage.py etl_sales --from 2026-09-08 --to 2026-09-22
docker compose exec web python manage.py etl_sales
docker compose exec web python manage.py etl_stock
docker compose exec web python manage.py etl_nightly

# Stage 3 SMS (local Excel is gitignored; SMS sent 2026-09-18)
docker compose exec web python manage.py import_sms_campaign --name "SMS 18 Sep 2026" --sent-on 2026-09-18 --to 2026-09-22

# Telegram-bot blast (users.csv = card,phone; gitignored; sent 2026-09-21).
# Run etl_dims first so Client.card_number (from ORGN.NAME) is filled.
docker compose exec web python manage.py etl_dims
docker compose exec web python manage.py import_tg_campaign --file data/local/users.csv --name "TG bot 21 Sep 2026" --sent-on 2026-09-21

# Stage 5 promos: example table is written to data/local/promos_example.xlsx and docs/promos_example.xlsx

# Django shell
docker compose exec web python manage.py shell

# Stop services
docker compose down

# Stop and remove volumes (fresh database)
docker compose down -v
```

## Production Deployment

Production runs on the **alt Debian** server (same pattern as `service-center-erp`). Deploy is done by the deploy hub — not from this machine:

```bash
# in ssh-alternative-server-connection
python scripts/deploy_app.py granit-analytics
```

### What this repo provides

| Artifact | Path |
|----------|------|
| Prod Compose (no local Postgres) | [`deploy/docker-compose.prod.yml`](./deploy/docker-compose.prod.yml) |
| Image | `ghcr.io/ivanbondarenkoit/granit-sales-analytics-erp:main` |
| Health | `GET /health` → `{"status":"ok","app":"granit-analytics"}` |
| Host health port | `127.0.0.1:8091` |
| Domain | `https://analytics.dimkava.ge` (Caddy `edge`) |

CI (`.github/workflows/ci-cd.yml`): on push to `main` — tests, then build/push GHCR `:main` and `:sha-…`. After the first successful push, set the GHCR package to **Public** so the server can pull without a login.

### Database (shared `pg-core`)

One database `granit`, schema **`analytics`** for this app (role `analytics`, `search_path = analytics, core`). Neighbor: `service-center-erp` uses schema `scerp`. Schema `core` is reserved for a future `granit-data-core` ETL (stage 2) — not used yet.

Hub places server `.env` next to prod compose. Required variables (see `.env.example`):

- `SECRET_KEY`, `DEBUG=False`
- `ALLOWED_HOSTS=analytics.dimkava.ge`
- `CSRF_TRUSTED_ORIGINS=https://analytics.dimkava.ge`
- `SESSION_COOKIE_SECURE=true`, `CSRF_COOKIE_SECURE=true`
- `DB_HOST=pg-core`, `DB_NAME=granit`, `DB_USER=analytics`, `DB_PASSWORD=…`, `DB_PORT=5432`, `DB_SSLMODE=disable`
- `PROXY_API_URL`, `PROXY_API_TOKEN` (for nightly ETL)
- `IMAGE_TAG=main` (or `sha-xxxxxxx` to pin/rollback)
- `ALLOW_REGISTRATION=true` for now; set `false` later to close public sign-up

Container entrypoint runs `migrate` + `compilemessages`, then gunicorn.

After first deploy, create an app user (once):

```bash
docker exec -it granit-analytics python manage.py createsuperuser
```

All UI routes require login. `/health` stays public for the hub healthcheck.

### After releasing the super-group matrix (once)

Migrate is automatic. Seed is **not** — run on the server after the new image is live:

```bash
docker exec granit-analytics python manage.py etl_dims
docker exec granit-analytics python manage.py seed_supergroups
# optional later: seed_supergroups --fill-unmapped
```

Hub operator notes: `ssh-alternative-server-connection/docs/DEPLOY-GRANIT-MATRIX.md`.

### Nightly ETL (alt cron via hub)

```bash
docker exec granit-analytics python manage.py etl_nightly
```

Cron (via hub catalog): **04:30 Asia/Tbilisi**. Command is idempotent and prints a summary to stdout (no secrets).
### Schema check (CI / local)

```bash
PG_ADMIN_URL=postgresql://postgres:postgres@localhost:5432/granit python scripts/check_pg_schema.py --reset
```

Ensures Django tables land in schema `analytics`, not `public`.

## Three Core Features

### 1. SMS Campaign Lift Analysis

Upload Excel with client IDs/phones (~1700 records). Analyze: did these clients make purchases during a specified period?

**Status:** Ready (STAGE 3) — Excel import, bought / not bought, catalog filters.

Telegram-bot blasts use the same screens: upload a CSV of `card,phone` with channel «Telegram bot». Clients are matched by loyalty card (Granit `ORGN.NAME`, 13 digits), then by phone.

### 2. Sales Explorer

List, group, sort, and filter sales by:
- Product, Product Group, Parameter
- Client, Store
- Date ranges

Built with Django + HTMX for fast, interactive filtering without frontend framework complexity.

**Status:** Ready (STAGE 4) — period slice, HTMX filters, group by product / group / production / store / client / day.

### 2b. Super-group matrix

Interactive matrix: super-group rows × store columns (qty + amount), shared membership editor, Excel export.
Seed from `sales/seed/supergroups.json` (from monthly-sales-report YAML). Catch-all row «Outside super-groups» keeps totals equal to all `SaleFact` lines.

```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_supergroups
# open /sales/matrix/
```

### 3. Promotion Effectiveness

Enter promotion details (SKU or group, date range). Analysis compares:
- Daily sales during promo
- vs. Pre-period baseline (median of N days before)
- vs. Year-over-year (YoY) same period
- Optional: Overlay forecast (from `granit-rests-pre-order` logic)

**Status:** Ready (STAGE 5) — Excel table or manual SKU/group, daily actual vs pre-period median vs YoY vs seasonal forecast.

## Development Stages

- [x] **STAGE 0:** Architecture plan finalized ([PLAN.md](./PLAN.md))
- [x] **STAGE 1:** Django skeleton + Docker + stub models + README
- [x] **STAGE 2:** ETL implementation (proxy → incremental + backfill)
- [x] **STAGE 3:** SMS campaign upload and analysis UI
- [x] **STAGE 4:** Sales explorer with HTMX filters
- [x] **STAGE 4b:** Super-group matrix (branch `feat/sales-supergroups` — merge to `main` to ship)
- [x] **STAGE 5:** Promo analysis with baseline/YoY comparison
- [x] **Alt deploy:** prep in repo (Compose/CI/GHCR) — ship via hub `deploy_app.py granit-analytics`
- [ ] **STAGE 6:** Optional alerts integration (notify-hub)

## Related Projects (Reference Only)

These projects provide architectural reference but are **not** dependencies:

- `granit-clients-based-segmentation` - Proxy access patterns, SMS campaigns
- `monthly-sales-report` - Sales slicing UI patterns
- `granit-rests-pre-order` - Forecast logic (seasonal index)
- `granit-product-sales-tracker` - Daily sales tracking

## Security Notes

- **Never commit secrets:** Use `.env` files (gitignored) or hub-managed server `.env`
- **Production database:** shared `pg-core` on Docker network `pgnet` (not exposed publicly)
- **Secret key:** unique per environment; placeholders starting with `replace-me` are rejected at startup
- **Proxy credentials:** only in `.env` on alt, not in git
## Contributing

1. Follow architecture in [PLAN.md](./PLAN.md)
2. Reference [CURSOR-PROMPT.md](./CURSOR-PROMPT.md) for implementation guidelines
3. Create feature branches for new work
4. Test locally with `docker compose` before pushing
5. Migrations must apply cleanly

## License

Internal project for Granit retail chain.
