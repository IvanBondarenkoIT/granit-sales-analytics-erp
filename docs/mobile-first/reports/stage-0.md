# Отчёт: этап 0 — демо-данные, скрипт скриншотов, сверка контракта

- Ветка: `feature/mobile-0-baseline`
- Коммит: *(заполняется после коммита)*
- Дата: 2026-11-24
- Итог: готово к ревью

## Что сделано

1. **Сверка контракта.** Пройдены инлайн-скрипты / `onchange` / `hx-*` и `assertContains` в тестах. В `RULES.md` §2–3 дописаны пробелы (auth lang, matrix `#scope`/`#store`, campaigns catalog filter, explorer shell + CDN HTMX, promo_edit = create, picker load-more / `tree-spacer` / site `category`, matrix_edit order actions; тестовые строки `coffee kg`, stock hint, `Live`/`Old`, фикстуры пикера, URL-assert’ы). Лишнего в RULES не удалял.
2. **`seed_ui_demo`.** `core/management/commands/seed_ui_demo.py`: отказ при `DEBUG=False` или непустой БД без `--force`; пользователи `demo_staff` / `demo_user` (пароль по умолчанию `demo-pass-123`); 5 магазинов (вкл. `HORECA TBILISI` и длинное имя), группы/товары, параметр «продукция», 446 строк продаж / 3 месяца / все `source`, остатки, `ensure_catalog` → 18 супергрупп, 3 месяца сверки (ok / bad / open), 2 кампании (SMS + Telegram, ~40 клиентов, часть с покупками), 3 акции (active / past / без анализа) + `analyze_promo` для графиков. Прогон: `seed_ui_demo --force` → OK.
3. **`scripts/ui_snapshots.py`.** Playwright Chromium, 390×844 и 1366×900, `demo_staff` + `demo_user`, `--locale`, `--compare`, метрики в `report.json`, `artifacts/` в `.gitignore`, `requirements-dev.txt`. Прогон: `python scripts/ui_snapshots.py --name baseline` → `artifacts/ui/baseline/` (100 страниц).
4. Проверки: `python manage.py test` → **90 OK**; seed + snapshots — см. выше.
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
- Скриншоты: `python scripts/ui_snapshots.py --name baseline` → `artifacts/ui/baseline/report.json` (+ PNG в `screenshots/`). `--compare` на этом этапе не вызывался (нет предыдущего прогона).
- Метрики из `report.json`, мобильная ширина **390 px**, пользователь `demo_staff` (для этапа 0 колонка «до → после» = факт baseline; «после» появится на следующих этапах):

| Страница | scrollWidth (cfg=390) | Полей &lt; 16px | Элементов &lt; 44px | Console | External |
|----------|------------------------|-----------------|---------------------|---------|----------|
| login | 390 (hscroll=no) | 5 | 4 | 0 | 0 |
| register | 775 | 4 | 6 | 0 | 0 |
| home | 775 | 4 | 6 | 0 | 0 |
| sales_default | 775 | 17 | 23 | 0 | 0 |
| sales_by_receipt | 775 | 17 | 53 | 0 | 0 |
| sales_scope_all | 775 | 17 | 17 | 0 | 0 |
| receipt | 775 | 4 | 3 | 0 | 0 |
| matrix | 776 | 7 | 55 | 0 | 0 |
| matrix_sg | 776 | 14 | 9 | 0 | 0 |
| matrix_group | 776 | 8 | 9 | 0 | 0 |
| matrix_edit | 776 | 265 | 145 | 0 | 0 |
| reconcile | 1024 | 6 | 7 | 0 | 0 |
| reconcile_month | 1158 | 7 | 7 | 0 | 0 |
| reconcile_docs | 980 | 6 | 6 | 1 (HTTP 500) | 0 |
| campaigns | 776 | 4 | 2 | 0 | 0 |
| campaign_detail | 776 | 9 | 11 | 0 | 0 |
| campaign_purchases | 776 | 6 | 5 | 0 | 0 |
| campaign_client | 776 | 6 | 5 | 0 | 0 |
| campaign_new | 905 | 12 | 9 | 0 | 0 |
| promos | 778 | 6 | 5 | 0 | 0 |
| promo_detail | 778 | 5 | 7 | 0 | 0 |
| promo_charts | 778 | 5 | 4 | 0 | 0 |
| promo_new | 778 | 22 | 20 | 0 | 0 |
| promo_edit | 778 | 21 | 17 | 0 | 0 |
| promo_picker | 778 | 22 | 31 | 0 | 0 |

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
- `--locale en` прогон скриншотов (код поддерживает; полный прогон не делался).
- Выгрузка Excel.
- `playwright install chromium` на этой машине потребовал `NODE_TLS_REJECT_UNAUTHORIZED=0` из‑за TLS к cdn.playwright.dev.
- Внешние запросы в `report.json` пустые (0), хотя в коде HTMX грузится с `unpkg.com` — в этом прогоне Playwright их не зафиксировал (возможно, кэш/блок сети контейнера). CDN по коду подтверждён.

## Найдено вне этапа (AUDIT vs факт)

**Подтвердилось аудитом:**

- Горизонтальный «переразмет» почти на всех экранах при cfg 390: `scrollWidth` 775–1158 (шапка `.nav` + широкие таблицы/тулбары).
- Много полей &lt; 16 px (explorer 17, promo form 20–22, matrix_edit **265**).
- Тап-зоны &lt; 44 px: язык, «Открыть», фильтры, кнопки матрицы/редактора (home: `select#language` 34 px высотой, ссылки «Открыть» 21 px).
- HTMX с unpkg в `sales/explorer.html` и `promos/create.html` (по коду).

**Не подтвердилось / иначе:**

- Аудит ожидал явный page-level horizontal scroll при innerWidth=390; фактически layout viewport часто расширяется до ширины контента — скролл страницы «внутри» 390 нужно мерить через configuredWidth (так и сделано в скрипте).

**Новое:**

- `/sales/reconcile/<month>/store/<id>/` → **HTTP 500** без Granit proxy (`month_documents`). Для UI-скриншотов страница падает; seed кладёт snapshot, но документы тянутся с proxy. В этапе 0 не чинил.
- На mobile кнопка `[data-open=picker-granit]` перекрыта полями `.grid` (pointer intercept) — клик Playwright timeout; открытие через `HTMLDialogElement.showModal()` работает.
- `ensure_catalog` создаёт полный каталог супергрупп из JSON (18), не «3–4» искусственных — для матрицы это полезнее; цвета/порядок из seed.

## Вопросы

нет (не блокировано)
