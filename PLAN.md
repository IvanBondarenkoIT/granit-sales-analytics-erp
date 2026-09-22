# План и сценарий: granit-sales-analytics-erp

**Статус:** зафиксировано 2026-09-22 (решение по архитектуре согласовано).  
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

---

## 2. Архитектура размещения (зафиксировано)

Гибрид: **новый Django-репо (B)** + **БД/ETL на alt, UI на Railway (улучшенный C)**.

| Компонент | Где | Зачем |
|-----------|-----|--------|
| PostgreSQL (warehouse) | **alt Debian** (~100 GB свободно) | На Windows remote часто 10–20 GB и переполняется |
| Nightly ETL | **alt** (cron / systemd) | Ночью ходит в firebird-db-proxy, пишет факты в Postgres |
| firebird-db-proxy | Windows у Granit | Боевой read-API; **не менять**, только клиент |
| Django + HTMX | **Railway** | Привычный UI-деплой; БД не держим на Railway |
| Полный дамп GDB | **Нет** | Только факты и справочники под три функции |

**Стек:** Python + Django + HTMX + Docker + PostgreSQL.

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

## 4. Безопасность Railway → Postgres на alt

Замысел: Railway видит Postgres на alt. У Postgres нет HTTP-токена — пользователь/пароль (+ TLS).

**Предпочтительно:** Cloudflare Tunnel / WireGuard / SSH-туннель — порт Postgres не в открытом интернете.

**Минимум, если порт снаружи:** нестандартный порт, роль `django_app` без SUPERUSER, `pg_hba` только egress IP Railway, `sslmode=require`, секреты только в Railway Variables / `.env` на alt (не в git).

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
| 1 | Skeleton Django+Docker + схема facts/dims + README деплоя alt/Railway | `docker compose` поднимает app локально против Postgres |
| 2 | ETL на alt: proxy → инкремент «вчера» + backfill истории | В БД есть продажи за выбранную глубину |
| 3 | SMS: импорт Excel → отчёт купили / не купили | Отчёт по тестовому Excel |
| 4 | Sales explorer (HTMX фильтры/группировки) | Срез за период без боли |
| 5 | Promos + baseline / YoY (+ optional forecast) | Вердикт по тестовой акции |
| 6 | Опционально: алерты в notify-hub | Не блокирует MVP |

---

## 7. Вне скоупа сейчас

- Переписывание segmentation / monthly-sales / proxy.
- Хостинг Postgres на Railway или тяжёлой БД на Windows remote.
- Полное зеркало ERP.
- Интеграция notify-hub (позже).

---

## 8. Открытые мелочи (не блокируют этап 1)

- [ ] Точный туннель Railway↔Postgres (Cloudflare Tunnel vs IP allowlist + TLS)
- [ ] Глубина истории backfill (N лет) после оценки размера

---

## 9. Связанные документы

- Cursor-промпт для реализации: `CURSOR-PROMPT.md` (в этом же репо).
