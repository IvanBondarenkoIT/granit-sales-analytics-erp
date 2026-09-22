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

Этап 1 (скелет) — **готово**. Дальше по `PLAN.md`, пока явно не сказано иное:

- **Не начинать этап 2 (ETL)** без явной команды.
- Следующий плановый кусок UI-инфры: **этап 1b** (i18n ru/en + переключатель), когда скажут делать.

Не делать пока: полный ETL, Excel SMS UI, деплой на Railway/alt, изменения в других репо — без явной команды.

## Критерий готовности этапа 1 (архив)

- `docker compose up` поднимает Django и Postgres.
- Миграции применяются.
- README описывает архитектуру из `PLAN.md`.

## Критерий готовности этапа 1b (когда войдём)

- `LANGUAGES = [("ru", …), ("en", …)]`, `LANGUAGE_CODE = "ru"`, LocaleMiddleware включён.
- Переключатель языка в общем layout; выбор сохраняется.
- Home (и общий chrome) переведены; `locale/` скомпилирован.
