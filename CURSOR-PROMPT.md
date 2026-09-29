# Cursor-промпт: granit-sales-analytics-erp

Использовать после этапа 0 (план зафиксирован). Редактировать по мере уточнений.

## Контекст

Репозиторий: `IvanBondarenkoIT/granit-sales-analytics-erp`.  
Продукт: лёгкое decision ERP для сети Granit (SMS lift, sales explorer, promo effectiveness).  
Архитектура и сценарий: см. `PLAN.md` в корне репо — **обязательно следовать**.

## Стек и размещение

- Python + Django + HTMX + Docker + PostgreSQL.
- **Прод:** всё на альт-сервере — UI-контейнер `granit-analytics` + общий `pg-core` (БД `granit`, схема `analytics`), Caddy `edge` → `analytics.dimkava.ge`.
- Образ: `ghcr.io/ivanbondarenkoit/granit-sales-analytics-erp:main`. Выкладка: deploy hub (`deploy_app.py granit-analytics`), не вручную.
- Источник данных: **firebird-db-proxy** на Windows у Granit (только клиент, proxy не менять).
- Не зеркалить весь GDB — только факты продаж/остатков и нужные измерения; живые SKU.
- **i18n:** UI на `ru` и `en` с переключателем (Django gettext + LocaleMiddleware). Дефолт `ru`. Строки UI только через `{% trans %}` / `gettext_lazy`; данные ERP не переводить. См. этап **1b** в `PLAN.md`.

## Эталоны (соседние репо на машине разработчика, READ-ONLY)

- `D:\CursorProjects\granit-clients-based-segmentation` — proxy ETL, SMS/campaigns, `campaign_attribution.py`.
- `D:\CursorProjects\monthly-sales-report` — срезы продаж.
- `D:\CursorProjects\granit-rests-pre-order` — `src/analysis/forecast.py`.
- `D:\CursorProjects\service-center-erp` — инфраструктура альта (compose/CI), не FastAPI-код.

## Ближайшая задача

Этапы 1–5 (MVP) — **готово**. Подготовка к альту (Dockerfile, prod-compose, CI→GHCR, `/health`, схема `analytics`) — в репо.

- **Не деплоить** на альт/Railway и не трогать сервер без явной команды (деплой — через хаб).
- **Не начинать этап 6 (алерты)** без явной команды.
- Этап 2 данных (`granit-data-core`, dim/fact в `core`) — не делать без команды.

Не делать пока: изменения в других репо — без явной команды.

## Критерий готовности этапа 1 (архив)

- `docker compose up` поднимает Django и Postgres.
- Миграции применяются.
- README описывает архитектуру из `PLAN.md`.

## Критерий готовности этапа 2 (архив)

- `etl_health` ходит в firebird-db-proxy.
- `etl_dims` / `etl_sales` / `etl_stock` / `etl_nightly` есть; секреты только в `.env`.
- В Postgres есть продажи за 12 месяцев.

## Критерий готовности этапа 4 (архив)

- `/sales/` режет `SaleFact` за период (дата по включительно).
- Фильтры: магазин, группа, товар, продукция, клиент, поиск по названию.
- Группировка: товар / группа / продукция / магазин / клиент / день; сортировка сумма / кол-во / имя.
- HTMX обновляет таблицу без перезагрузки; лейблы ru+en.

## Критерий готовности этапа 5 (архив)

- `/promos/` заводит акцию из Excel (group_id / product_id) или вручную.
- Дневной факт vs медиана pre-period vs медиана YoY vs сезонный прогноз (без pandas).
- Карточка ru+en с вердиктом % к базе и YoY.

## Критерий готовности этапа 1b (архив)

- `LANGUAGES = [("ru", …), ("en", …)]`, `LANGUAGE_CODE = "ru"`, LocaleMiddleware включён.
- Переключатель языка в общем layout; выбор сохраняется.
- Home (и общий chrome) переведены; `locale/` скомпилирован.
