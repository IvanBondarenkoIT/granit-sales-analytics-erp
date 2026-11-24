# Отчёт: этап 0 — демо-данные, скрипт скриншотов, сверка контракта

- Ветка: `feature/mobile-0-baseline`
- Коммит: `8acf0a7`
- Дата: 2026-11-24
- Итог: готово к ревью (после исправлений по `reviews/stage-0.md`)

## Что сделано

1. **Сверка контракта.** Пройдены инлайн-скрипты / `onchange` / `hx-*` и `assertContains` в тестах. В `RULES.md` §2–3 дописаны пробелы (auth lang, matrix `#scope`/`#store`, campaigns catalog filter, explorer shell + CDN HTMX, promo_edit = create, picker load-more / `tree-spacer` / site `category`, matrix_edit order actions; тестовые строки `coffee kg`, stock hint, `Live`/`Old`, фикстуры пикера, URL-assert’ы). Лишнего в RULES не удалял.
2. **`seed_ui_demo`.** `core/management/commands/seed_ui_demo.py`: отказ при `DEBUG=False` или непустой БД без `--force`; отказ, если `DATABASES["default"]["HOST"]` не локальный (`db` / localhost / `127.0.0.1` / `::1` / пусто) — обход только через `--allow-host`; пользователи `demo_staff` / `demo_user` (пароль по умолчанию `demo-pass-123`); 5 магазинов (вкл. `HORECA TBILISI` и длинное имя), группы/товары, параметр «продукция», 446 строк продаж / 3 месяца / все `source`, остатки, `ensure_catalog` → 18 супергрупп, 3 месяца сверки (ok / bad / open), 2 кампании (SMS + Telegram, ~40 клиентов, часть с покупками), 3 акции (active / past / без анализа) + `analyze_promo` для графиков. Прогон: `seed_ui_demo --force` → OK (`host='db'`).
3. **`scripts/ui_snapshots.py`.** Playwright Chromium, 390×844 и 1366×900, `demo_staff` + `demo_user`, `--locale`, `--compare`, метрики в `report.json`, `artifacts/` в `.gitignore`, `requirements-dev.txt`. Прогоны: `baseline` (ru) и `baseline-en` (en) → по 100 страниц. `reconcile_docs` помечен `expectedError: needs Granit proxy` и исключён из подсветки регрессий в `compare.html`.
4. Проверки: `python manage.py test` → **90 OK** (на первом прогоне этапа); seed + snapshots — см. выше и раздел «Исправления по ревью».
5. В корневом `README.md` — раздел «UI screenshots».

## Изменённые файлы

```text
.gitignore
README.md
requirements-dev.txt
core/management/__init__.py
core/management/commands/__init__.py
core/management/commands/seed_ui_demo.py
scripts/ui_snapshots.py
docs/mobile-first/*   (рабочая папка + STATUS/RULES/report)
```

## Проверки

- `python manage.py test`: **90 tests OK** (Postgres через `docker compose`).
- Скриншоты: `python scripts/ui_snapshots.py --name baseline` → `artifacts/ui/baseline/`; `--locale en --name baseline-en` → `artifacts/ui/baseline-en/`. `--compare` на этапе 0 не вызывался.
- Метрики из `report.json` (ru baseline после rework), мобильная ширина **390 px**, пользователь `demo_staff`. На `/sales/` и `/promos/new/` `externalRequests` содержат `unpkg.com/htmx.org@1.9.12`. `reconcile_docs` — `expectedError`, не в сводке регрессий:

| Страница | scrollWidth (cfg=390) | Полей &lt; 16px | Элементов &lt; 44px | Console | External |
|----------|------------------------|-----------------|---------------------|---------|----------|
| login | 390 (hscroll=no) | 5 | 4 | 0 | 0 |
| register | 775 | 4 | 6 | 0 | 0 |
| home | 775 | 4 | 6 | 0 | 0 |
| sales_default | 775 | 17 | 23 | 0 | 2 (unpkg htmx) |
| sales_by_receipt | 775 | 17 | 53 | 0 | 2 |
| sales_scope_all | 775 | 17 | 17 | 0 | 2 |
| receipt | 775 | 4 | 3 | 0 | 0 |
| matrix | 776 | 7 | 55 | 0 | 0 |
| matrix_sg | 776 | 14 | 9 | 0 | 0 |
| matrix_group | 776 | 8 | 9 | 0 | 0 |
| matrix_edit | 776 | 265 | 145 | 0 | 0 |
| reconcile | 1024 | 6 | 7 | 0 | 0 |
| reconcile_month | 1158 | 7 | 7 | 0 | 0 |
| reconcile_docs (expected: needs Granit proxy) | 980 | 6 | 6 | 1 (HTTP 500) | 0 |
| campaigns | 776 | 4 | 2 | 0 | 0 |
| campaign_detail | 776 | 9 | 11 | 0 | 0 |
| campaign_purchases | 776 | 6 | 5 | 0 | 0 |
| campaign_client | 776 | 6 | 5 | 0 | 0 |
| campaign_new | 905 | 12 | 9 | 0 | 0 |
| promos | 778 | 6 | 5 | 0 | 0 |
| promo_detail | 778 | 5 | 7 | 0 | 0 |
| promo_charts | 778 | 5 | 4 | 0 | 0 |
| promo_new | 778 | 22 | 20 | 0 | 2 (unpkg htmx) |
| promo_edit | 778 | 21 | 17 | 0 | 2 |
| promo_picker | 778 | 22 | 31 | 0 | 2 |

Замечание по замеру: на mobile Chromium `window.innerWidth` часто растёт вместе с контентом; `hasHorizontalScroll` считается как `scrollWidth > min(innerWidth, configuredWidth=390)`.

- Десктоп 1366 px: без горизонтального скролла страницы на всех снятых экранах; UI без изменений (этап 0 UI не трогал).

## Изменения в тестах

нет

## Отклонения от RULES.md

- Новый Python: только `seed_ui_demo` (разрешено промптом этапа 0).
- UI / views / urls не менялись.

## Что проверить руками на телефоне

- Логин `demo_staff` / `demo-pass-123`, пробежаться по нижним пунктам будущего меню: продажи, матрица, сверка, кампании, акции.
- Открыть пикер на `/promos/new/` («Добавить из Гранита») — на узком экране кнопка перекрывается полями формы (скрипт открывает dialog через `showModal()`).
- Сверка → месяц → документы магазина: ожидаем ошибку без firebird proxy (см. ниже).

## Не проверено

- Реальный телефон / iOS Safari.
- Выгрузка Excel.
- `playwright install chromium` на этой машине потребовал `NODE_TLS_REJECT_UNAUTHORIZED=0` из‑за TLS к cdn.playwright.dev (в README/скрипты не добавляли).
- `baseline-en` снят; детальную таблицу en-метрик в отчёт не копировал — лежит в `artifacts/ui/baseline-en/report.json`.

## Найдено вне этапа (AUDIT vs факт)

**Подтвердилось аудитом:**

- Горизонтальный «переразмет» почти на всех экранах при cfg 390: `scrollWidth` 775–1158 (шапка `.nav` + широкие таблицы/тулбары).
- Много полей &lt; 16 px (explorer 17, promo form 20–22, matrix_edit **265**).
- Тап-зоны &lt; 44 px: язык, «Открыть», фильтры, кнопки матрицы/редактора (home: `select#language` 34 px высотой, ссылки «Открыть» 21 px).
- HTMX с unpkg в `sales/explorer.html` и `promos/create.html` (по коду).

**Не подтвердилось / иначе:**

- Аудит ожидал явный page-level horizontal scroll при innerWidth=390; фактически layout viewport часто расширяется до ширины контента — скролл страницы «внутри» 390 нужно мерить через configuredWidth (так и сделано в скрипте).

**Новое:**

- `/sales/reconcile/<month>/store/<id>/` → **HTTP 500** без Granit proxy (`month_documents`). Seed кладёт snapshot, документы тянутся с proxy. В скрипте помечено `expectedError`. **На проде при недоступном proxy пользователь тоже получит 500, а не сообщение об ошибке** — отдельная задача вне mobile-first.
- На mobile кнопка `[data-open=picker-granit]` перекрыта полями `.grid` (pointer intercept) — с телефона нельзя добавить товары в акцию (зафиксировано в AUDIT / этап 7). Скриншот пикера открывается через `showModal()`.
- `ensure_catalog` создаёт полный каталог супергрупп из JSON (18), не «3–4» искусственных — так лучше.

## Исправления по ревью

По `reviews/stage-0.md`:

1. **`externalRequests`:** баг копирования списка до `goto` исправлен — в `_capture` передаётся живой список, снимок после загрузки. Повторный `baseline`: на `sales_*` / `promo_new` / `promo_picker` / `promo_edit` — `https://unpkg.com/htmx.org@1.9.12` (+ `/dist/htmx.min.js`).
2. **`seed_ui_demo` host guard:** отказ на нелокальный `HOST`; `--allow-host` для явного обхода; в логе/ошибке печатаются `host` и `name`. Проверено: `host='db'` OK; симуляция `pg-core.example` → `CommandError`.
3. **`reconcile_docs`:** `expectedError: "needs Granit proxy"`; в логе `[SKIP]`; в `compare.html` серая строка, без подсветки регрессии.
4. **`--locale en`:** `python scripts/ui_snapshots.py --name baseline-en --locale en` → `artifacts/ui/baseline-en/` (100 страниц, `locale=en`).

## Вопросы

нет (не блокировано)
