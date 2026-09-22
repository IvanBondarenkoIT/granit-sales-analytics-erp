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

## Эталоны (соседние репо на машине разработчика, READ-ONLY)

- `D:\CursorProjects\granit-clients-based-segmentation` — proxy ETL, SMS/campaigns, `campaign_attribution.py`.
- `D:\CursorProjects\monthly-sales-report` — срезы продаж.
- `D:\CursorProjects\granit-rests-pre-order` — `src/analysis/forecast.py`.

## Ближайшая задача (этап 1)

Скелет приложения в этом репо:

1. Django-проект + приложения-заготовки: `core`, `etl`, `campaigns`, `sales`, `promos`.
2. Docker Compose: `web` + `db` (Postgres) для локальной разработки.
3. Модели-заготовки facts/dims (можно пустые поля-заглушки с комментариями под Granit ids).
4. README: как поднять локально; как задуманы alt ETL и Railway (без секретов).
5. `.env.example` без реальных паролей.

Не делать пока: полный ETL, Excel SMS UI, деплой на Railway/alt, изменения в других репо.

## Критерий готовности этапа 1

- `docker compose up` поднимает Django и Postgres.
- Миграции применяются.
- README описывает архитектуру из `PLAN.md`.
