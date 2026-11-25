# Отчёт: этап 7 — Акции и итоговая проверка

- Ветка: `feature/mobile-7-promos`
- Коммит: *(см. STATUS.md после коммита)*
- Дата: 2026-11-25
- Итог: готово к ревью

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
 locale/en/LC_MESSAGES/django.mo
 locale/en/LC_MESSAGES/django.po
 locale/ru/LC_MESSAGES/django.mo
 locale/ru/LC_MESSAGES/django.po
 promos/templates/promos/charts.html
 promos/templates/promos/create.html
 promos/templates/promos/detail.html
 promos/templates/promos/list.html
```

## Проверки

- `DB_HOST=localhost python manage.py test`: **93 tests OK** (≈32–39 s).
- Скриншоты: `python scripts/ui_snapshots.py --name stage7 --compare baseline` → `artifacts/ui/stage7/compare.html` (104 pages, exit 0); `--locale en` → `artifacts/ui/stage7-en/`. Перед прогонами `docker compose restart web`.
- Внешние запросы: **0** на всех страницах stage7.
- Метрики mobile 390 px, `demo_staff`, **baseline → stage7**:

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
| reconcile_docs | 980 → 980 | 6 → 2 | 6 → 6 |
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

Исключения tap < 44 (осознанно):
- `promo_new` / `promo_picker`: нативный `input[type=checkbox]` 18–20 px (`use_example_file`, `inactive`); label `.check-row` / `.picker-filter label` ≥ 44 px.
- `campaign_new`: тот же паттерн чекбокса (этап 6).
- `login`: select языка (этап 2).
- `reconcile_docs`: страница 980 px без полного stub-контента документов (вне этапа 7; как на 5–6).

Скролл внутри `.scroll-x` (матрица «Table», SVG графиков) — допустим; page `scrollWidth` 390.

- Десктоп 1366 px: таблицы акций снова table; пикер с деревом слева и тремя кнопками футера; форма пересчёта кампаний и фильтры обозревателя на месте (см. ниже).

### Проверка глазами (desktop, demo_staff, stage7)

| Скриншот | Что видно |
|----------|-----------|
| `artifacts/ui/stage7/screenshots/promos__demo_staff__desktop.png` | Заголовок, «Новая акция», чипы Active/Passed, таблица с колонками Тип / к базе |
| `artifacts/ui/stage7/screenshots/promo_detail__demo_staff__desktop.png` | Мета, цели, Пересчитать/Графики, KPI, таблица цен 8 колонок |
| `artifacts/ui/stage7/screenshots/promo_new__demo_staff__desktop.png` | Поля формы, кнопки «Добавить из Гранита/сайта», Save |
| `artifacts/ui/stage7/screenshots/promo_edit__demo_staff__desktop.png` | Строка группы Coffee kg, без ложного «Товаров пока нет», Save |
| `artifacts/ui/stage7/screenshots/promo_picker__demo_staff__desktop.png` | Дерево слева, «Добавить выбранные (0)» + Add all + Done |
| `artifacts/ui/stage7/screenshots/promo_charts__demo_staff__desktop.png` | Empty-state «нет расчёта» + Пересчитать (демо-акция #12 без analyses) |
| `artifacts/ui/stage7/screenshots/sales_default__demo_staff__desktop.png` | Фильтры, Group by / Sort by, таблица |
| `artifacts/ui/stage7/screenshots/campaign_detail__demo_staff__desktop.png` | Дата пересчёта + кнопка, селекты каталога |
| `artifacts/ui/stage7/screenshots/matrix__demo_staff__desktop.png` | Тулбар scope/дат/Apply/Excel/редактор |
| `artifacts/ui/stage7/screenshots/reconcile__demo_staff__desktop.png` | KPI, карточки месяцев, таблица услуг |

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
- Скриншот charts с заполненными SVG: discovery взял promo #12 (draft без analyses); на списке lift у #10 (AUTUMN) виден. Графики с данными — проверить руками на `/promos/10/charts/`.

## Найдено вне этапа

- `reconcile_docs` на 390 px: scrollWidth 980 (без полного stub документов) — как на этапах 5–6.
- Discovery `ui_snapshots` предпочитает первый promo с ссылкой charts, даже без analyses — для демо графиков лучше якорить AUTUMN SALE.

## Вопросы

нет
