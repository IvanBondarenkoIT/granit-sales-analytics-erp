# Cursor-промпт: granit-sales-analytics-erp

Использовать после этапа 0 (план зафиксирован). Редактировать по мере уточнений.

## Контекст

Репозиторий: `IvanBondarenkoIT/granit-sales-analytics-erp`.  
Продукт: лёгкое decision ERP для сети Granit (SMS lift, sales explorer, promo effectiveness).  
Архитектура и сценарий: см. `PLAN.md` в корне репо — **обязательно следовать**.

## Стек и размещение

- Python + Django + HTMX + Docker + PostgreSQL.
- Postgres + nightly ETL: **alt Debian**.
- Django UI: **Railway**.
- Источник данных: **firebird-db-proxy** на Windows у Granit (только клиент, proxy не менять).
- Не зеркалить весь GDB — только факты продаж/остатков и нужные измерения; живые SKU.
- **i18n:** UI на `ru` и `en` с переключателем (Django gettext + LocaleMiddleware). Дефолт `ru`. Строки UI только через `{% trans %}` / `gettext_lazy`; данные ERP не переводить. См. этап **1b** в `PLAN.md`.

## Эталоны (соседние репо на машине разработчика, READ-ONLY)

- `D:\CursorProjects\granit-clients-based-segmentation` — proxy ETL, SMS/campaigns, `campaign_attribution.py`.
- `D:\CursorProjects\monthly-sales-report` — срезы продаж.
- `D:\CursorProjects\granit-rests-pre-order` — `src/analysis/forecast.py`.

## Ближайшая задача

Этапы 1, **1b (i18n)** и **2 (ETL)** — **готово** (локальный Postgres, proxy client, backfill 12 мес). Дальше по `PLAN.md`:

- **Не начинать этап 3 (SMS Excel UI)** без явной команды.
- Не деплоить на alt/Railway без явной команды.

Не делать пока: Excel SMS UI, деплой на Railway/alt, изменения в других репо — без явной команды.

## Критерий готовности этапа 1 (архив)

- `docker compose up` поднимает Django и Postgres.
- Миграции применяются.
- README описывает архитектуру из `PLAN.md`.

## Критерий готовности этапа 2 (архив)

- `etl_health` ходит в firebird-db-proxy.
- `etl_dims` / `etl_sales` / `etl_stock` / `etl_nightly` есть; секреты только в `.env`.
- В Postgres есть продажи за 12 месяцев.

## Критерий готовности этапа 1b (архив)

- `LANGUAGES = [("ru", …), ("en", …)]`, `LANGUAGE_CODE = "ru"`, LocaleMiddleware включён.
- Переключатель языка в общем layout; выбор сохраняется.
- Home (и общий chrome) переведены; `locale/` скомпилирован.
