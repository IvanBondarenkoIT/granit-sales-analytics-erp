# Granit Sales Analytics ERP

Lightweight decision ERP for Granit retail chain: SMS campaign lift analysis, sales explorer, and promotion effectiveness tracking.

## Architecture Overview

This project follows a hybrid deployment architecture (see [PLAN.md](./PLAN.md) for full details):

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| **PostgreSQL** (warehouse) | **alt Debian** | Data warehouse (~100 GB available), stores sales facts and dimensions |
| **Nightly ETL** | **alt Debian** (cron/systemd) | Pulls data from firebird-db-proxy, loads into Postgres |
| **Django + HTMX UI** | **Railway** | Web application for analytics and reporting |
| **firebird-db-proxy** | Windows at Granit | Read-only API to Granit ERP (external, not modified) |

### Technology Stack

- **Backend:** Python + Django 4.2+
- **Frontend:** HTMX (lightweight, server-rendered)
- **Database:** PostgreSQL 15+
- **Deployment:** Docker + Docker Compose (local), Railway (production UI)
- **ETL:** Python scripts running on alt Debian

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
├── docker-compose.yml     # Local development environment
├── Dockerfile             # Application container definition
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

4. **Create superuser (optional, for Django admin):**

In a new terminal:

```bash
docker compose exec web python manage.py createsuperuser
```

5. **Access the application:**

- Web UI: http://localhost:8000
- Django Admin: http://localhost:8000/admin

### Development Commands

```bash
# View logs
docker compose logs -f web

# Run migrations
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate

# Django shell
docker compose exec web python manage.py shell

# Stop services
docker compose down

# Stop and remove volumes (fresh database)
docker compose down -v
```

## Production Deployment

### Database (alt Debian)

PostgreSQL runs on alt Debian server with ~100 GB available:

```bash
# Install PostgreSQL
sudo apt-get install postgresql-15

# Create database and user
sudo -u postgres psql
CREATE DATABASE granitanalytics;
CREATE USER django_app WITH PASSWORD 'secure-password';
GRANT ALL PRIVILEGES ON DATABASE granitanalytics TO django_app;
```

**Security:**
- Use non-standard port or tunnel (Cloudflare Tunnel / WireGuard / SSH)
- Configure `pg_hba.conf` to restrict access
- Enable `sslmode=require` for connections
- Never commit credentials to git

### ETL Scripts (alt Debian)

ETL scripts run nightly on alt Debian via cron:

```bash
# Example cron entry (runs at 2 AM)
0 2 * * * /path/to/venv/bin/python /path/to/etl_script.py >> /var/log/granit-etl.log 2>&1
```

ETL connects to:
- **Source:** firebird-db-proxy API on Windows
- **Target:** Local PostgreSQL on alt

See `etl/` app for ETL tracking models. Full ETL implementation in STAGE 2.

### Web UI (Railway)

Django application deploys to Railway:

1. Connect Railway to this GitHub repository
2. Set environment variables in Railway dashboard:
   - `SECRET_KEY` (generate new secure key)
   - `DEBUG=False`
   - `ALLOWED_HOSTS=your-app.railway.app`
   - Database connection (either Railway Postgres or alt Debian via tunnel):
     - `DB_NAME`
     - `DB_USER`
     - `DB_PASSWORD`
     - `DB_HOST` (alt IP or tunnel endpoint)
     - `DB_PORT`

Railway will automatically build and deploy on git push.

## Three Core Features

### 1. SMS Campaign Lift Analysis

Upload Excel with client IDs/phones (~1700 records). Analyze: did these clients make purchases during a specified period?

**Status:** Models ready, UI pending (STAGE 3)

### 2. Sales Explorer

List, group, sort, and filter sales by:
- Product, Product Group, Parameter
- Client, Store
- Date ranges

Built with Django + HTMX for fast, interactive filtering without frontend framework complexity.

**Status:** Models ready, UI pending (STAGE 4)

### 3. Promotion Effectiveness

Enter promotion details (SKU or group, date range). Analysis compares:
- Daily sales during promo
- vs. Pre-period baseline (median of N days before)
- vs. Year-over-year (YoY) same period
- Optional: Overlay forecast (from `granit-rests-pre-order` logic)

**Status:** Models ready, analysis logic pending (STAGE 5)

## Development Stages

- [x] **STAGE 0:** Architecture plan finalized ([PLAN.md](./PLAN.md))
- [x] **STAGE 1:** Django skeleton + Docker + stub models + README ← **YOU ARE HERE**
- [ ] **STAGE 2:** ETL implementation (proxy → incremental + backfill)
- [ ] **STAGE 3:** SMS campaign upload and analysis UI
- [ ] **STAGE 4:** Sales explorer with HTMX filters
- [ ] **STAGE 5:** Promo analysis with baseline/YoY comparison
- [ ] **STAGE 6:** Optional alerts integration (notify-hub)

## Related Projects (Reference Only)

These projects provide architectural reference but are **not** dependencies:

- `granit-clients-based-segmentation` - Proxy access patterns, SMS campaigns
- `monthly-sales-report` - Sales slicing UI patterns
- `granit-rests-pre-order` - Forecast logic (seasonal index)
- `granit-product-sales-tracker` - Daily sales tracking

## Security Notes

- **Never commit secrets:** Use `.env` files (gitignored) or Railway environment variables
- **Production database:** Secure with tunnels, non-standard ports, and TLS
- **Secret key:** Generate unique key for production, never use default
- **Proxy credentials:** Stored securely on alt Debian, not in this repo

## Contributing

1. Follow architecture in [PLAN.md](./PLAN.md)
2. Reference [CURSOR-PROMPT.md](./CURSOR-PROMPT.md) for implementation guidelines
3. Create feature branches for new work
4. Test locally with `docker compose` before pushing
5. Migrations must apply cleanly

## License

Internal project for Granit retail chain.
