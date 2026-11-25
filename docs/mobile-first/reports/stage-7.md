# Отчёт: этап 7 — Акции и итоговая проверка

- Ветка: `feature/mobile-7-promos`
- Коммит: *(tip после rework — см. STATUS.md)*
- Дата: 2026-11-25
- Итог: готово к ревью (после rework)

## Что сделано

1. **Список `/promos/`.** Вкладки Active/Passed → чипы `.promo-tabs`. Таблица → `.table-cards--compact.promo-list`: название (stretched link), период, тип; справа «к базе ±N%» цветом через тег `{% promo_lift_pre %}` (из prefetched `analyses`, без правки view). «Новая акция» — sticky над нижним меню; на ≥ 900 px — в `.page-head`.
2. **Карточка акции.** Шапка (период, дни базы, тип); format/channels мелко; заметки и цели — `<details>` (на ≥ 900 px `open` через `matchMedia`, summary скрыт). KPI-плитки 2 в ряд: Факт → к базе % → к YoY % → Прогноз → базы. «Пересчитать» / «Графики» — две кнопки ≥ 44 px. Цены → `.table-cards.price-cards` (название + сайт/нет связи; строки себест./розница/акция/маржа и остаток/заработок; итог карточкой). Дни → `.table-cards--compact.days-cards`.
3. **Графики.** Без правки `charts.py`: обёртка `.scroll-x`, у `svg.chart` на < 600 px `min-width: 640px`, `font-size: 14px`, прореживание подписей X через `<g class="x-labels"> text:nth-child(2n)`, легенда 2 колонки. Класс `chart` первым. Подписи на узком экране читаемы при горизонтальном скролле внутри обёртки (не страницы).
4. **Форма.** Убрано перекрытие кнопок пикера (`.section`/`.actions` выше `.grid` по z-index; одна колонка на телефоне). `sel-table` → карточки CSS поверх `tr/td` (JS не тронут). «Удалить» ≥ 44 px. «Сохранить и проанализировать» — sticky + `form="promo-form"`, `disabled` после submit. Пустая строка `#selected-empty[hidden]` скрыта и на десктопе.
5. **Пикер.** На < 900 px: `100dvh` + safe-area, липкие head/foot; дерево в `<details class="picker-tree-panel">` («Группа: … ▾»), при выборе узла сворачивается; футер: «Добавить выбранные» на всю ширину, вторичные рядом. На ≥ 900 px: дерево слева (`open` через JS, `display: contents`), три кнопки футера видны. `ul.tree-children` — сосед `.tree-toggle`.
6. **Итоговая проверка.** `ui_snapshots --name stage7 --compare baseline` и `--locale en` → `stage7-en`. В `RULES.md` добавлен §7 «Паттерны для новых экранов» (каркас, фильтр, details+JS, KPI, table-cards + stretched link, scroll-x, sticky, чипы).

## Изменённые файлы

```text
 core/templatetags/ui.py
 docs/mobile-first/RULES.md
 docs/mobile-first/STATUS.md
 docs/mobile-first/reports/stage-7.md
 docs/mobile-first/reviews/stage-7.md
 locale/en/LC_MESSAGES/django.mo
 locale/en/LC_MESSAGES/django.po
 locale/ru/LC_MESSAGES/django.mo
 locale/ru/LC_MESSAGES/django.po
 promos/templates/promos/charts.html
 promos/templates/promos/create.html
 promos/templates/promos/detail.html
 promos/templates/promos/list.html
 scripts/ui_snapshots.py
```

## Проверки

- `DB_HOST=localhost python manage.py test`: **93 tests OK** (≈32 s) после rework.
- Скриншоты: `python scripts/ui_snapshots.py --name stage7 --compare baseline` → `artifacts/ui/stage7/compare.html` (**108** pages: +`promo_charts_empty`, exit 0). Discovery: `promo_id=10` (AUTUMN SALE), `promo_charts_empty=12`. Для `reconcile_docs` — stub `:8765` + временный compose override `PROXY_API_URL=http://host.docker.internal:8765` (не в репо); после прогона web без stub.
- Внешние запросы: **0**.
- Метрики mobile 390 px, `demo_staff`, **baseline → stage7** (после rework):

| Страница | Гор. скролл (scrollWidth) до → после | Полей < 16px до → после | Элементов < 44px до → после |
|----------|--------------------------------------|-------------------------|------------------------------|
| login | 390 → 390 | 5 → 0 | 4 → 1 |
| register | 775 → 390 | 4 → 0 | 6 → 0 |
| home | 775 → 390 | 4 → 0 | 6 → 0 |
| more | — → 390 | — → 0 | — → 0 |
| sales_default | 775 → 390 | 17 → 0 | 23 → 0 |
| sales_by_receipt | 775 → 390 | 17 → 0 | 53 → 0 |
| sales_scope_all | 775 → 390 | 17 → 0 | 17 → 0 |
| receipt | 775 → 390 | 4 → 0 | 3 → 0 |
| matrix | 776 → 390 | 7 → 0 | 55 → 0 |
| matrix_edit | 776 → 390 | 265 → 0 | 145 → 0 |
| matrix_sg | 776 → 390 | 14 → 0 | 9 → 0 |
| matrix_group | 776 → 390 | 8 → 0 | 9 → 0 |
| reconcile | 1024 → 390 | 6 → 0 | 7 → 0 |
| reconcile_month | 1158 → 390 | 7 → 0 | 7 → 0 |
| reconcile_docs | 980 → 390 | 6 → 0 | 6 → 0 |
| campaigns | 776 → 390 | 4 → 0 | 2 → 0 |
| campaign_new | 905 → 390 | 12 → 0 | 9 → 1 |
| campaign_detail | 776 → 390 | 9 → 0 | 11 → 0 |
| campaign_purchases | 776 → 390 | 6 → 0 | 5 → 0 |
| campaign_client | 776 → 390 | 6 → 0 | 5 → 0 |
| promos | 778 → 390 | 6 → 0 | 5 → 0 |
| promo_new | 778 → 390 | 22 → 0 | 20 → 1 |
| promo_picker | 778 → 390 | 22 → 0 | 31 → 2 |
| promo_detail | 778 → 390 | 5 → 0 | 7 → 0 |
| promo_edit | 778 → 390 | 21 → 0 | 17 → 0 |
| promo_charts | 778 → 390 | 5 → 0 | 4 → 0 |
| promo_charts_empty | — → 390 | — → 0 | — → 0 |

Исключения tap < 44 (осознанно):
- `promo_new` / `promo_picker`: нативный `input[type=checkbox]` 18–20 px (`use_example_file`, `inactive`); label ≥ 44 px.
- `campaign_new`: тот же паттерн чекбокса (этап 6).
- `login`: select языка (этап 2).

Скролл внутри `.scroll-x` (матрица «Table», SVG графиков) — допустим; page `scrollWidth` 390 на всех страницах выше.

- Десктоп 1366 px: таблицы акций снова table; пикер с деревом слева и тремя кнопками футера; форма пересчёта кампаний и фильтры обозревателя на месте.

### Проверка глазами (desktop / mobile charts, demo_staff, stage7)

| Скриншот | Что видно |
|----------|-----------|
| `artifacts/ui/stage7/screenshots/promos__demo_staff__desktop.png` | Заголовок, «Новая акция», чипы, таблица |
| `artifacts/ui/stage7/screenshots/promo_detail__demo_staff__desktop.png` | AUTUMN SALE #10: KPI с цифрами, таблица цен |
| `artifacts/ui/stage7/screenshots/promo_charts__demo_staff__desktop.png` | SVG с данными (не empty-state) |
| `artifacts/ui/stage7/screenshots/promo_charts__demo_staff__mobile.png` | см. «Исправления по ревью» |
| `artifacts/ui/stage7/screenshots/promo_charts_empty__demo_staff__mobile.png` | черновик #12: empty-state + Пересчитать |
| `artifacts/ui/stage7/screenshots/reconcile_docs__demo_staff__mobile.png` | документы со stub, scrollWidth 390 |

## Изменения в тестах

нет

## Отклонения от RULES.md

нет (только шаблоны, `locale/`, тег отображения `promo_lift_pre`, документация)

## Что проверить руками на телефоне

1. `/promos/` — чипы Active/Passed; тап по карточке → detail; lift зелёный/красный у AUTUMN SALE.
2. Detail — цели/заметки свёрнуты; Пересчитать и Графики в ряд; карточки цен.
3. Create — кнопки «Добавить из Гранита/сайта» нажимаются; пикер на весь экран; дерево сворачивается после выбора группы; Save внизу, повторный submit блокируется.
4. Charts на акции с расчётом (AUTUMN SALE) — SVG скроллится внутри `.scroll-x`, подписи читаемы.
5. ≥ 900 px — табличный список/detail, пикер как раньше с тремя кнопками.

## Не проверено

- Реальный телефон / Safari.

## Найдено вне этапа

- Формула «к базе %» дублируется в `promos/views.py::_lift` и теге `promo_lift_pre` (ревью: к сведению).

## Вопросы

нет

## Исправления по ревью

Код ревью: `640a8e8` / tip `5cb6104` → rework (`reviews/stage-7.md`).

1. **Графики с данными.** В `scripts/ui_snapshots.py` discovery выбирает акцию с `.days-cards tbody tr` (`promo_with_charts` / `promo_id` = #10 AUTUMN SALE); черновик без analyses → отдельный job `promo_charts_empty` (#12). Перегон `stage7` vs `baseline` (108 pages).
2. **Проверка глазами** `artifacts/ui/stage7/screenshots/promo_charts__demo_staff__mobile.png` (`/promos/10/charts/`, scrollWidth **390**, hasHorizontalScroll **false**):
   - легенда (Факт / База / Прогноз / Дни акции) в 2 колонки — читается;
   - подписи осей Y читаемы; X прорежены (`03.11`, `13.11`, …), друг на друга не налезают;
   - page не скроллится по горизонтали — скролл широкого SVG только внутри `.scroll-x`.
   `charts.py` не трогали; `blocked` не нужен.
3. **reconcile_docs.** Поднят `scripts/stub_granit_proxy.py` (`:8765`, token `local-stub`); web временно на `host.docker.internal:8765`. Строка сводной: **980 → 390**, font 0, tap 0. После прогона web без stub-override.
