# Промпт / план проекта — актуально в PLAN.md

Этот файл сохранён для совместимости с первым коммитом.

**Актуальный зафиксированный план и сценарий:** [`PLAN.md`](./PLAN.md)  
**Промпт для Cursor (этап 1+):** [`CURSOR-PROMPT.md`](./CURSOR-PROMPT.md)

Кратко (2026-09-22):

- Репо: `granit-sales-analytics-erp` (новый контур, не наращиваем segmentation).
- Postgres + nightly ETL на **alt**; Django+HTMX на **Railway**; данные через **firebird-db-proxy**.
- Три функции: SMS lift, sales explorer, promo vs pre-period / YoY (+ optional forecast).
