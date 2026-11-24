# Отчёт: этап 2 — каркас, навигация, главная

- Ветка: `feature/mobile-2-shell`
- Коммит: `2fa4297` (код: `c9c6fbc`)
- Дата: 2026-11-24
- Итог: готово к ревью

## Что сделано

0. **Долги этапа 1.** В `scripts/ui_snapshots.py` метрика полей < 16 px пропускает `input[type=hidden|checkbox|radio|color|file]`. В `static/css/app.css` убран `font-size: 16px !important`; `min-height: var(--tap)` у полей/кнопок остаётся в базе (телефон), с `@media (min-width: 900px)` плотность сброшена (`min-height: unset`, компактные padding, `font-size: inherit` у полей).
1. **Плашка 52 px** в `templates/base.html`: `{% block back_url %}` (пустой href → кнопка скрыта), `{% block page_title %}`, аватар с инициалами → `/more/#profile`. Ссылки «← …» помечены `.page-back`, заголовки — `.page-h1` (скрыты < 900 px).
2. **Нижнее меню** + safe-area: Продажи · Супергруппы · Акции · Кампании · Ещё; иконки через `templates/partials/icon.html`; активность по тем же `request.path`, что у `.nav`. `.topbar` и `footer` скрыты на телефоне, показаны ≥ 900 px.
3. **`/more/`**: view `more` в `core/views.py`, URL `path("more/", ...)`, шаблон `core/more.html` (сверка, главная, новая акция/кампания, редактор супергрупп, Django-админка для staff, `#profile` с языком и выходом). Тесты в `core/tests.py`. Ссылка Admin Panel в футере — только `is_staff` (иначе `assertNotContains(admin:index)` ломался из‑за футера в HTML).
4. **Главная**: плитки 2×N с иконкой и описанием; hero и MVP только ≥ 900 px.
5. **Десктоп ≥ 900 px**: верхнее меню, язык, выход, футер; без плашки и нижнего меню.
6. **`page_title` / `back_url`** проставлены во всех страницах на `base.html` (см. карту в промпте). `auth_base` не менялся по отступам — login уже 390; register стал 390 за счёт отсутствия десктоп-топбара в auth (раньше скролл давала общая ширина? — register 775→390 в прогоне).

## Изменённые файлы

```text
 .../templates/campaigns/client_purchases.html      |    6 +-
 campaigns/templates/campaigns/create.html          |    5 +-
 campaigns/templates/campaigns/detail.html          |    6 +-
 campaigns/templates/campaigns/list.html            |    3 +-
 campaigns/templates/campaigns/purchases.html       |    6 +-
 core/templates/core/home.html                      |  134 +-
 core/templates/core/more.html                      |   new
 core/tests.py                                      |   21 +
 core/views.py                                      |    9 +
 docs/mobile-first/STATUS.md                        |    2 +-
 docs/mobile-first/reports/stage-2.md               |   new
 granitanalytics/urls.py                            |    3 +-
 locale/en/LC_MESSAGES/django.mo                    |  Bin
 locale/en/LC_MESSAGES/django.po                    |  (makemessages refresh)
 locale/ru/LC_MESSAGES/django.mo                    |  Bin
 locale/ru/LC_MESSAGES/django.po                    |  (makemessages refresh)
 promos/templates/promos/*.html                     |    ~
 sales/templates/sales/*.html                       |    ~
 scripts/ui_snapshots.py                            |    2 +
 static/css/app.css                                 |  252 +-
 templates/base.html                                |   42 +-
 templates/partials/icon.html                       |   new
```

## Проверки

- `DB_HOST=localhost python manage.py test`: **93 tests OK**
- Скриншоты RU: `python scripts/ui_snapshots.py --name stage2 --compare stage1` → `artifacts/ui/stage2/` (+ `compare.html`)
- Скриншоты EN: `python scripts/ui_snapshots.py --name stage2-en --locale en` → `artifacts/ui/stage2-en/`
- Перед прогоном: `docker compose exec web python manage.py collectstatic --noinput`, `docker compose restart web`
- Метрики из `report.json`, mobile 390 px, `demo_staff` (без `reconcile_docs` — expectedError):

| Страница | Гор. скролл (scrollWidth) до → после | Полей < 16px до → после | Элементов < 44px до → после |
|----------|--------------------------------------|-------------------------|------------------------------|
| login | 390 → 390 | 0 → 0 | 1 → 1 |
| register | 775 → 390 | 0 → 0 | 5 → 0 |
| home | 775 → 390 | 0 → 0 | 5 → 0 |
| sales_default | 775 → 487 | 0 → 0 | 9 → 8 |
| sales_by_receipt | 775 → 546 | 0 → 0 | 39 → 38 |
| sales_scope_all | 775 → 421 | 0 → 0 | 3 → 2 |
| matrix | 776 → 390 | 0 → 0 | 47 → 46 |
| matrix_edit | 776 → 600 | 0 → 0 | 20 → 18 |
| reconcile | 1008 → 1008 | 0 → 0 | 5 → 3 |
| campaigns | 776 → 494 | 0 → 0 | 1 → 0 |
| campaign_new | 841 → 390 | 0 → 0 | 2 → 1 |
| promos | 778 → 390 | 0 → 0 | 1 → 0 |
| promo_new | 778 → 390 | 0 → 0 | 6 → 4 |
| promo_picker | 778 → 390 | 0 → 0 | 7 → 5 |
| receipt | 775 → 390 | 0 → 0 | 2 → 0 |
| matrix_sg | 776 → 390 | 0 → 0 | 2 → 0 |
| matrix_group | 776 → 390 | 0 → 0 | 6 → 3 |
| reconcile_month | 1142 → 1142 | 0 → 0 | 5 → 3 |
| campaign_detail | 776 → 524 | 0 → 0 | 4 → 2 |
| campaign_purchases | 776 → 524 | 0 → 0 | 2 → 0 |
| campaign_client | 776 → 524 | 0 → 0 | 2 → 0 |
| promo_detail | 778 → 390 | 0 → 0 | 4 → 1 |
| promo_edit | 778 → 390 | 0 → 0 | 2 → 0 |
| promo_charts | 778 → 390 | 0 → 0 | 2 → 0 |

Каркас без широких таблиц даёт `scrollWidth = 390` (home, matrix, promos, receipt, …). Остаточный горизонтальный скролл — таблицы/сверка/обозреватель/кампании (этапы 3–7).

EN: home/matrix/promos = 390; campaigns 429 (короче подписи). Подписи нижнего меню на en: Sales / Super-groups / Promos / Campaigns / More.

- Десктоп 1366 px: верхнее меню на месте; `matrix_edit` снова компактнее по плотности полей (долг stage-1). Метрика desktop: `smallFontInputs`/`smallTapCount` выросли там, где снова `font-size: inherit` и без принудительных 44 px — ожидаемо.

## Изменения в тестах

- `core/tests.py`: три теста на `/more/` (anon → login; plain user без `admin:index`; staff с админкой).

## Отклонения от RULES.md

- Разрешённые: view + URL `/more/`.
- Футер: ссылка Admin Panel только для `is_staff` (нужно для теста и согласуется с переносом админки в «Ещё»).
- В `core/views.py` у элементов `apps` добавлено поле `icon` (только отображение главной).

## Что проверить руками на телефоне

1. Нижнее меню: 5 пунктов, активный подсвет, подписи в одну строку на ru и en.
2. Плашка: назад на чеке/супергруппе/акции; аватар → `/more/#profile`.
3. «Ещё»: сверка, новые сущности, редактор; у staff — Django-админка; язык и выход.
4. Главная: плитки 2 в ряд, без hero; на десктопе — hero + MVP.
5. Десктоп ≥ 900: старое верхнее меню, без нижней панели.

## Не проверено

- Реальный телефон / iOS safe-area.
- Push ветки / PR.

## Найдено вне этапа

- `reconcile_docs` по-прежнему expectedError (коллизия warehouse/store) — этап 5.
- Широкие таблицы (sales, campaigns, reconcile) всё ещё дают page h-scroll — этапы 3–7.
- На desktop после сброса плотности метрика «полей < 16» снова ненулевая на части экранов — следствие `font-size: inherit`, не регрессия телефона.

## Вопросы

нет
