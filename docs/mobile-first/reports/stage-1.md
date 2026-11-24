# Отчёт: этап 1 — фундамент

- Ветка: `feature/mobile-1-foundation`
- Коммит: `b2f5f38` (код: `17866f4`)
- Дата: 2026-11-24
- Итог: готово к ревью

## Что сделано

1. **Общий CSS.** Создан [`static/css/app.css`](../../static/css/app.css): `:root` переменные (`--brand`/`--brand-dark`, статусы, `--gap`, `--radius`, `--tap: 44px`, `--bar-h`, `--nav-h`, `--nav-pad-bottom` + safe-area). База — телефон; расширения `@media (min-width: 600/900/1200px)`. `container` padding `1rem` → `2rem` с 900px. Общие `.btn`/`.btn-secondary`/`.btn-link`/`.btn-danger`, `.hint`/`.help`/`.muted`/`.empty`, `.stats`/`.stat`, таблицы/`.num`, `.ok`/`.bad`/`.up`/`.down`, shell (topbar/nav/flash/lang/footer). В шаблонах дубли удалены, оставлено screen-specific.
2. **Static + settings.** `STATICFILES_DIRS = [BASE_DIR / "static"]` в [`granitanalytics/settings.py`](../../granitanalytics/settings.py). Подключение через `{% static %}` в `base.html` и `auth_base.html`. `collectstatic --noinput` — OK (172 файла).
3. **Без CDN.** `static/vendor/htmx-1.9.12.min.js` (1.9.12); один `<script>` в `base.html`. Unpkg убран из `sales/explorer.html` и `promos/create.html`. Select-filter JS вынесен в `static/js/app.js`.
4. **Поля / клавиатуры.** `font-size: 16px !important` на все `input`/`select`/`textarea` (иначе hidden/checkbox/color давали ложные <16 в метрике). `type="text"` + key attrs в `matrix_edit`; `inputmode="numeric"` у Client ID и `pre_period_days`; `enterkeyhint="search"` у поисков; `autocapitalize="off"` у логина/ключа SG.
5. **Тап-зоны.** `min-height: var(--tap)` у кнопок, lang-switch, logout, `.btn-link`, `.btn-order`, части picker/tree controls. Часть мелких ссылок в таблицах/nav остаётся <44 — раскладка экранов не в этом этапе.
6. **Safe-area / PWA.** `viewport-fit=cover`, `theme-color=#667eea`, `static/manifest.webmanifest`, иконки 192/512. SW не добавлялся.

## Изменённые файлы

```text
 .gitignore                                         |   3 +
 campaigns/templates/campaigns/client_purchases.html|   6 +-
 campaigns/templates/campaigns/create.html          |   9 +-
 campaigns/templates/campaigns/detail.html          |  15 +-
 campaigns/templates/campaigns/list.html            |   5 -
 campaigns/templates/campaigns/purchases.html       |   5 +-
 core/forms.py                                      |   2 +
 docs/mobile-first/STATUS.md                        |   2 +-
 docs/mobile-first/reports/stage-1.md               |  92 +++++
 granitanalytics/settings.py                        |   1 +
 promos/forms.py                                    |   1 +
 promos/templates/promos/charts.html                |   8 +-
 promos/templates/promos/create.html                |  22 +-
 promos/templates/promos/detail.html                |  13 +-
 promos/templates/promos/list.html                  |   9 +-
 sales/templates/sales/_explorer.html               |   8 +-
 sales/templates/sales/_reconcile_style.html        |   6 +-
 sales/templates/sales/explorer.html                |  14 +-
 sales/templates/sales/matrix.html                  |   9 +-
 sales/templates/sales/matrix_edit.html             |  50 +--
 sales/templates/sales/matrix_group.html            |   9 +-
 sales/templates/sales/matrix_sg.html               |   9 +-
 sales/templates/sales/receipt.html                 |   5 +-
 static/css/app.css                                 | 444 +++++++++++++++++++++
 static/icons/icon-192.png                          | Bin
 static/icons/icon-512.png                          | Bin
 static/js/app.js                                   |  19 +
 static/manifest.webmanifest                        |  23 ++
 static/vendor/htmx-1.9.12.min.js                   |   1 +
 templates/base.html                                | 100 +----
 templates/registration/auth_base.html              |  49 +--
 31 files changed, 669 insertions(+), 270 deletions(-)
```

## Проверки

- `DB_HOST=localhost python manage.py test`: **90 tests OK**
- `python manage.py collectstatic --noinput`: OK
- Скриншоты: `python scripts/ui_snapshots.py --name stage1 --compare baseline` → `artifacts/ui/stage1/` (+ `compare.html`). Перед прогоном нужен `docker compose restart web` (runserver в volume на Windows не всегда подхватывает шаблоны без рестарта).
- Метрики 390 px, `demo_staff` (reconcile_docs — expectedError, не в таблице):

| Страница | Гор. скролл (scrollWidth) до → после | Полей < 16px до → после | Элементов < 44px до → после |
|----------|--------------------------------------|-------------------------|------------------------------|
| login | 390 → 390 | 5 → 0 | 4 → 1 |
| register | 775 → 775 | 4 → 0 | 6 → 5 |
| home | 775 → 775 | 4 → 0 | 6 → 5 |
| sales_default | 775 → 775 | 17 → 0 | 23 → 9 |
| sales_by_receipt | 775 → 775 | 17 → 0 | 53 → 39 |
| sales_scope_all | 775 → 775 | 17 → 0 | 17 → 3 |
| matrix | 776 → 776 | 7 → 0 | 55 → 47 |
| matrix_edit | 776 → 776 | 265 → 0 | 145 → 20 |
| reconcile | 1024 → 1008 | 6 → 0 | 7 → 5 |
| campaigns | 776 → 776 | 4 → 0 | 2 → 1 |
| campaign_new | 905 → 841 | 12 → 0 | 9 → 2 |
| promos | 778 → 778 | 6 → 0 | 5 → 1 |
| promo_new | 778 → 778 | 22 → 0 | 20 → 6 |
| promo_picker | 778 → 778 | 22 → 0 | 31 → 7 |
| receipt | 775 → 775 | 4 → 0 | 3 → 2 |
| matrix_sg | 776 → 776 | 14 → 0 | 9 → 2 |
| matrix_group | 776 → 776 | 8 → 0 | 9 → 6 |
| reconcile_month | 1158 → 1142 | 7 → 0 | 7 → 5 |
| campaign_detail | 776 → 776 | 9 → 0 | 11 → 4 |
| campaign_purchases | 776 → 776 | 6 → 0 | 5 → 2 |
| campaign_client | 776 → 776 | 6 → 0 | 5 → 2 |
| promo_detail | 778 → 778 | 5 → 0 | 7 → 4 |
| promo_edit | 778 → 778 | 21 → 0 | 17 → 2 |
| promo_charts | 778 → 778 | 5 → 0 | 4 → 2 |

- Внешние запросы: **0** на всех страницах (было 2× unpkg на sales/promo HTMX).
- Десктоп 1366 px: без горизонтального скролла страницы; кнопки выровнены к общему `.btn`; заметных регрессий раскладки нет (сравнивать `artifacts/ui/stage1/compare.html`).

## Изменения в тестах

нет

## Отклонения от RULES.md

- Python: только `STATICFILES_DIRS` и `widget.attrs` в `core/forms.py` / `promos/forms.py` (разрешено промптом этапа 1).
- URLs / `hx-*` / `data-*` / `name` / `id` / views / models не менялись.

## Что проверить руками на телефоне

- Логин: поля без iOS-зума при фокусе; язык и «Выйти» удобно тапаются.
- `/sales/`: фильтры HTMX без CDN (офлайн-сеть / DevTools → Network без unpkg).
- `/promos/new/`: пикер открывается, поиск с `enterkeyhint=search`.
- PWA: Add to Home Screen / manifest (имя, иконка, theme-color).

## Не проверено

- Реальный телефон (только Playwright Chromium 390×844).
- Locale `en` для stage1 (baseline-en есть с этапа 0; stage1 снимался `ru`).
- Выгрузка Excel.

## Найдено вне этапа

- Горизонтальный скролл страницы на большинстве экранов (nav + широкие таблицы) — этапы 2–3+.
- Тап-зоны <44 остались у части ссылок в ячейках таблиц, nav, мелких действий — чинить с раскладкой экранов.
- Пикер «Добавить из Гранита» перекрыт `.grid` на 390 px (этап 7 / AUDIT).
- `reconcile_docs` → 500 без Granit proxy (этап 5).
- После правок шаблонов на Windows нужен `docker compose restart web`, иначе runserver отдаёт старый HTML.

## Вопросы

нет
