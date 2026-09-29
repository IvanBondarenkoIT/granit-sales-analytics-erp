# Промпт для Cursor: подготовка granit-sales-analytics-erp к деплою на альт-сервер

Скопируй блок ниже в чат Cursor, открыв этот репозиторий.

---

Подготовь granit-sales-analytics-erp к продакшену на альт-сервере и настрой CI/CD.
Сам деплой **не запускай** — его делает deploy hub:

- хаб: `D:\CursorProjects\ssh-alternative-server-connection`
- команда: `python scripts/deploy_app.py granit-analytics`
- архитектура: `D:\CursorProjects\ssh-alternative-server-connection\docs\ARCHITECTURE-ALT.md`

## Что меняем (важно)

Раньше в `PLAN.md` было: Postgres/ETL на альт, **UI на Railway** + туннель к БД.
Это **отменяем**. Делаем так же, как уже сделали для **service-center-erp** (соседний репо, уже в проде на https://service.dimkava.ge).

| | service-center-erp (готовый образец) | granit-analytics (делаем так же) |
|---|---|---|
| Где UI | альт-сервер, Docker-контейнер | альт-сервер, Docker-контейнер |
| Где БД | общий `pg-core`, база `granit` | **тот же** `pg-core`, та же база `granit` |
| Схема / роль | `scerp` / `scerp` | `analytics` / `analytics` |
| Домен | `service.dimkava.ge` → Caddy `edge` | `analytics.dimkava.ge` → Caddy `edge` |
| Порт на хосте (только health) | `127.0.0.1:8090` | `127.0.0.1:8091` |
| Образ | `ghcr.io/ivanbondarenkoit/service-center-erp:main` | `ghcr.io/ivanbondarenkoit/granit-sales-analytics-erp:main` |
| Обновление | push в `main` → GHCR → cron `app-update` каждые 5 мин | то же |
| Railway | демо можно оставить, **прод не через него** | то же |

**Общий Postgres уже поднят.** Одна база `granit`, разные схемы:

| Схема | Кто пишет | Статус |
|---|---|---|
| `core` | будущий `granit-data-core` (ночь) | пока пустая |
| `scerp` | service-center-erp | **уже в проде** |
| `analytics` | это приложение | ваша зона |

Роль `analytics`: `search_path = analytics, core`; на `core` только `SELECT`; писать только в `analytics`; в `public` ничего не создавать.

Подключение (пароль положит хаб в серверный `.env`):

```
DB_HOST=pg-core
DB_NAME=granit
DB_USER=analytics
DB_PASSWORD=<хаб>
DB_PORT=5432
DB_SSLMODE=disable
```

**Образец паттерна (не копируй FastAPI-код — только инфраструктуру):**

- `D:\CursorProjects\service-center-erp\deploy\docker-compose.prod.yml`
- `D:\CursorProjects\service-center-erp\.github\workflows\ci-cd.yml`
- `D:\CursorProjects\service-center-erp\docs\CURSOR-PROMPT-ALT-DEPLOY.md`

Паттерн: образ из GHCR, сети `pgnet` + `edge` (external), healthcheck на `/health`, **без своего Postgres** в прод-compose.

У scerp после деплоя всплыла ловушка схем: при `search_path = app, core` одноимённая таблица в `core` мешала создать свою в схеме приложения. У них починили явной привязкой к схеме (`bc8b405`). У Django проверь, что `migrate` создаёт `django_*` / ваши таблицы **в `analytics`**, не в `public`.

## Этапы

**Этап 1 (сейчас):** приложение на pg-core в схеме `analytics`. ETL (`etl_*`) остаётся в этом репо и пишет в `analytics` — как сейчас, только БД общая на сервере.

**Этап 2 (позже, `granit-data-core`):** dim/fact переезжают в `core`, модели здесь `managed = False`, cron `etl_nightly` отсюда уходит. Этап 2 **не делать**, но не усложнять переезд: не хардкодить схему в SQL, держать имена в `db_table`.

## Что сделать (этап 1)

### 1. Настройки БД (`granitanalytics/settings.py`)

- Оставить `DB_*`, добавить `DB_SSLMODE` (по умолчанию `disable`) и `DB_SEARCH_PATH` (по умолчанию пусто — тогда работает `search_path` роли):

```python
OPTIONS = {"sslmode": os.getenv("DB_SSLMODE", "disable")}
if os.getenv("DB_SEARCH_PATH"):
    OPTIONS["options"] = f"-c search_path={os.getenv('DB_SEARCH_PATH')}"
```

- Исправить `.env.example`: убрать/поправить упоминание `DATABASE_URL`, если код его не читает. Описать для альта: `DB_HOST=pg-core`, `DB_NAME=granit`, `DB_USER=analytics`, `DB_PORT=5432`, `DB_SSLMODE=disable`.
- Проверить, что `migrate` создаёт таблицы (включая `django_*`, `auth_*`) в схеме `analytics`.

### 2. Продакшен-настройки Django

- `DEBUG=False` по умолчанию в проде; `SECRET_KEY` обязателен (без слабого дефолта в проде).
- `ALLOWED_HOSTS=analytics.dimkava.ge`, `CSRF_TRUSTED_ORIGINS=https://analytics.dimkava.ge` (из env).
- За прокси (как у scerp с Caddy): `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`, `USE_X_FORWARDED_HOST = True`.
- `SESSION_COOKIE_SECURE` и `CSRF_COOKIE_SECURE` из env (`true` на сервере, локально `false`).
- Статика: `whitenoise` (middleware сразу после `SecurityMiddleware`), `STATIC_ROOT = BASE_DIR / "staticfiles"`, `collectstatic` при сборке образа.
- `/health` без авторизации: `{"status": "ok", "app": "granit-analytics"}` + `SELECT 1` в БД.

### 3. Dockerfile

- gunicorn на `${PORT:-8000}`, `--forwarded-allow-ips='*'`, 2–3 воркера.
- Entrypoint: `python manage.py migrate --noinput` (+ `compilemessages`, если нужно), затем gunicorn.
- Обход `--trusted-host` для pip убрать из прод-сборки, если он был только для Windows; локально — через build-arg.

### 4. `deploy/docker-compose.prod.yml` (новый; локальный `docker-compose.yml` не трогать)

Как у scerp: **нет сервиса `db`**, только приложение + внешние сети.

```yaml
name: granit-analytics

services:
  web:
    image: ghcr.io/ivanbondarenkoit/granit-sales-analytics-erp:${IMAGE_TAG:-main}
    container_name: granit-analytics
    restart: unless-stopped
    env_file:
      - .env
    environment:
      PORT: "8000"
      TZ: Asia/Tbilisi
    ports:
      - "127.0.0.1:8091:8000"
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - pgnet
      - edge

networks:
  pgnet:
    external: true
  edge:
    external: true
```

Ночной ETL на этапе 1 хаб повесит cron: `docker exec granit-analytics python manage.py etl_nightly` (03:00 Asia/Tbilisi). Команда должна быть идемпотентной и писать понятный итог в stdout (без секретов).

### 5. CI/CD: push в `main` = автовыкладка

Создать `.github/workflows/ci-cd.yml` по образцу scerp (`D:\CursorProjects\service-center-erp\.github\workflows\ci-cd.yml`):

- на PR — тесты;
- на push в `main` — тесты, затем build/push `ghcr.io/ivanbondarenkoit/granit-sales-analytics-erp:main` и `:sha-<short>`;
- `docker/metadata-action` + `docker/build-push-action`, `GITHUB_TOKEN` с `packages: write`.

Для тестов в CI: сервис `postgres:16` в workflow **или** SQLite-настройки для тестов (как удобнее; главное — зелёный CI без секретов из `.env`).

После первого успешного push: GitHub → Packages → пакет → **Public** (серверу логин в GHCR не нужен).

Выкладка: сервер каждые 5 минут `pull` `:main`, перезапуск, ожидание `/health`, при провале откат. Ручной откат: `IMAGE_TAG=sha-xxxxxxx` в `.env` на сервере.

Миграции при старте контейнера — только обратно совместимые.

### 6. Документация

- `PLAN.md`: убрать «UI на Railway + туннель». Размещение — всё на альт-сервере; общий pg-core / схема `analytics`; соседство со `service-center-erp` (схема `scerp`); `edge` на `analytics.dimkava.ge`; ETL → `granit-data-core` на этапе 2.
- `README.md`: раздел «Продакшен» вместо apt-Postgres и Railway как прод.
- `CURSOR-PROMPT.md`: правило «не деплоить без явной команды» оставить.

## Ограничения

- Не деплоить и не трогать сервер; Railway-демо не выключать.
- Не коммитить секреты (`.env`, `PROXY_API_TOKEN`, пароли).
- Тесты зелёные перед коммитом.
- В конце — список изменений и что нужно от хаба (переменные `.env`, пароль роли `analytics`), чтобы деплой запустили из хаба.
