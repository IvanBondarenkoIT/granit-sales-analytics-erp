# План и сценарий: granit-sales-analytics-erp

**Статус:** зафиксировано 2026-09-22; обновлено 2026-09-29 (прод на альт: pg-core / схема `analytics`, без Railway).  
**Репо:** https://github.com/IvanBondarenkoIT/granit-sales-analytics-erp  
**Локально:** `D:\CursorProjects\granit-sales-analytics-erp`

Лёгкое «decision ERP» для Granit: SMS-кампании, срезы продаж, оценка акций.  
Не замена учётной ERP. Не раздуваем `granit-clients-based-segmentation` — новый контур, эталоны только как ориентиры.

---

## 1. Цели продукта (три функции)

1. **Эффект SMS-кампании**  
   Вход: Excel (телефоны + id клиентов, ориентир ~1700).  
   Вопрос: были ли продажи у этих клиентов за выбранный период.

2. **UI аналитики продаж**  
   Список / группировка / сортировка за период: товар, группа, параметр («продукция»), клиент, магазин.  
   UI: Django + HTMX, без перегруза.

3. **Анализ акций**  
   Вход: таблица акций (SKU или группа).  
   Через 1–2 недели: факт по дням vs медиана pre-period vs медиана того же окна год назад (YoY).  
   Опционально: overlay прогноза (логика из `granit-rests-pre-order`: recent mean × seasonal median index).

4. **Двуязычный UI (EN / RU)**  
   Весь пользовательский интерфейс — на английском и русском с явным переключателем языка.  
   Данные ERP (названия товаров, магазинов и т.п.) не переводим: показываем как в источнике.

---

## 2. Архитектура размещения (зафиксировано)

Всё на **альт-сервере** (как `service-center-erp`), не Railway + туннель.

| Компонент | Где | Зачем |
|-----------|-----|--------|
| PostgreSQL `pg-core` | **альт**, Docker-сеть `pgnet` | Общая БД `granit`; схемы `core` / `scerp` / `analytics` |
| Схема `analytics` | роль `analytics` | Таблицы этого приложения (этап 1 ETL пишет сюда же) |
| Схема `scerp` | service-center-erp | Соседнее приложение на том же Postgres |
| Схема `core` | будущий `granit-data-core` | Общие dim/fact (этап 2); пока пустая, только SELECT |
| Nightly ETL | **альт** cron → `docker exec … etl_nightly` | Ночью ходит в firebird-db-proxy |
| firebird-db-proxy | Windows у Granit | Боевой read-API; **не менять**, только клиент |
| Django + HTMX | **альт**, контейнер `granit-analytics` | Образ GHCR; сеть `edge` (Caddy) → `analytics.dimkava.ge` |
| Полный дамп GDB | **Нет** | Только факты и справочники под три функции |

**Прод-порт health на хосте:** `127.0.0.1:8091`. Образ: `ghcr.io/ivanbondarenkoit/granit-sales-analytics-erp:main`.  
Выкладка через deploy hub (`deploy_app.py granit-analytics`), не вручную с этой машины.

**Стек:** Python + Django + HTMX + Docker + PostgreSQL.

**i18n (зафиксировано):** Django gettext (`{% trans %}` / `gettext_lazy`), `LocaleMiddleware`, cookie/session для выбора языка.  
Языки: `ru`, `en`. Язык по умолчанию: **`ru`**. Переключатель в общем layout (без отдельных зеркальных URL на каждый экран).  
Каталоги: `locale/ru/LC_MESSAGES/`, `locale/en/LC_MESSAGES/`. Новые UI-экраны сразу с ключами перевода, не хардкод строк в шаблонах.

**RAM на alt:** мало — допустимо. Мало одновременных пользователей; ETL ночью одним процессом; скромные настройки Postgres; при необходимости позже PgBouncer.

**Windows remote** в этой схеме — источник данных через proxy, не дом для warehouse.

---

## 3. Модель данных (принцип)

Узкий слепок, можно с длинной историей продаж:

- **Факты:** строки продаж (дата, магазин, клиент, товар, qty, sum, …); остатки «на вчера» по живым SKU.
- **Измерения:** товар, группа, параметр «продукция» (id=2 в эталоне), магазин, клиент (минимум полей).
- Не тянуть мёртвый ассортимент без продаж и без остатка.
- Без BLOB/вложений; при росте — помесячные партиции.
- Глубину backfill (N лет) оценить по размеру фактов на первом ETL.

---

## 4. Безопасность и доступ к Postgres

UI и БД в одной Docker-сети `pgnet` на альте — наружу Postgres не светим. Caddy `edge` терминирует HTTPS на `analytics.dimkava.ge`.

Роль `analytics`: `search_path = analytics, core`; писать только в `analytics`; на `core` только `SELECT`; в `public` ничего не создавать. Пароль и `.env` кладёт deploy hub (не в git).

**Этап 2 (позже):** dim/fact переезжают в `core` (`granit-data-core`), модели здесь `managed = False`, cron ETL уходит из этого репо. Пока не делать; не хардкодить схему в SQL.

---

## 5. Эталоны (READ-ONLY, не копировать целиком)

| Проект | Что брать |
|--------|-----------|
| `granit-clients-based-segmentation` | Доступ через proxy (`REMOTE`), кампании/SMS, `campaign_attribution.py`, param «продукция» |
| `monthly-sales-report` | Идеи срезов магазин × группы (UI-паттерны; стек FastAPI+Vite не обязателен) |
| `granit-rests-pre-order` | `src/analysis/forecast.py` — сезонный индекс, не ML |
| `granit-product-sales-tracker` | Дневные продажи + TG; прогноза нет — слабее для forecast |
| `firebird-db-proxy` | Только клиент |

---

## 6. Сценарий реализации (MVP по этапам)

| Этап | Что делаем | Критерий готовности |
|------|------------|---------------------|
| 0 | Этот план в репо | Документ согласован (готово) |
| 1 | Skeleton Django+Docker + схема facts/dims + README деплоя на альт | `docker compose` поднимает app локально против Postgres (готово) |
| 1b | i18n: `ru`/`en`, LocaleMiddleware, переключатель в layout, базовые строки home/admin chrome | Переключение языка сохраняется в сессии; home на обоих языках (готово) |
| 2 | ETL: proxy → инкремент «вчера» + backfill 12 мес (команды Django; alt cron позже) | В локальном Postgres продажи `2025-09-22`–`2026-09-21` (готово) |
| 3 | SMS: импорт Excel → отчёт купили / не купили (строки UI через gettext) | Отчёт по списку от 18.09.2026, окно с даты рассылки (готово) |
| 3b | Telegram-бот: CSV `карта,телефон` → та же кампания (канал `telegram`), матч по карте из `ORGN.NAME` | Рассылка 21.09.2026 отдельной кампанией (готово) |
| 4 | Sales explorer (HTMX фильтры/группировки), UI двуязычный | Срез за период без боли; фильтры/лейблы ru+en (готово) |
| 4b | Матрица супергрупп × магазины + редактор состава (общий) + Excel | Сверка итогов с SaleFact; сид из YAML родителя (в разработке на ветке) |
| 5 | Promos + baseline / YoY (+ optional forecast), UI двуязычный | Вердикт по тестовой акции; экран ru+en (готово) |
| 6 | Опционально: алерты в notify-hub | Не блокирует MVP |

---

## 7. Вне скоупа сейчас

- Переписывание segmentation / monthly-sales / proxy.
- Хостинг Postgres или UI на Railway (демо можно оставить; прод — альт).
- Полное зеркало ERP.
- Интеграция notify-hub / этап 6 (позже).
- Перенос dim/fact в схему `core` (этап 2 / `granit-data-core`).

---

## 8. Открытые мелочи (не блокируют MVP)

- [x] Глубина backfill: **12 месяцев** (первый прогон: 365 дней, ~156k строк `fact_sale`)
- [x] Прод-размещение: альт + pg-core / `analytics` (подготовка в репо; выкладка — хаб)
- [ ] Нужен ли `uk` (украинский) позже — сейчас только `ru` + `en`

---

## 9. Связанные документы

- Cursor-промпт для реализации: `CURSOR-PROMPT.md` (в этом же репо).
- Промпт подготовки к альту: `docs/CURSOR-PROMPT-ALT-DEPLOY.md`.
- Deploy hub: `ssh-alternative-server-connection` (`deploy_app.py granit-analytics`).
