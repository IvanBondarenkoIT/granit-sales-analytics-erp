# Отчёт: этап 6 — Кампании

- Ветка: `feature/mobile-6-campaigns`
- Коммит: `b01707e`
- Дата: 2026-11-25
- Итог: готово к ревью

## Что сделано

1. **Список `/campaigns/`.** Таблица → `.table-cards--compact.campaign-list`: название со stretched-link (`.tc-primary a::after`), бейдж канала, дата отправки + период мелко, справа «N из M» и %. «Новая кампания» — fixed-панель над нижним меню на телефоне; на ≥ 900 px — кнопка в `.page-head` как раньше.
2. **Карточка кампании.** Шапка компактно (бейдж + sent + period). «Пересчитать» — `<details class="recalc-panel">` (на ≥ 900 px тело видно без summary через CSS `:not([open])`). KPI: «Доля купивших» первой на всю ширину, остальные 2 в ряд. `_catalog_filter.html` — свёрнутая строка-фильтр как на этапе 3. Статус-фильтры — чипы со скроллом, активный по `status` (`all` / `bought` / `not_bought`). Клиенты → `.table-cards--compact`: имя (или ID) + карта/ID мелко, справа сумма и Да/Нет цветом; «Состав заказа» — тап по карточке (stretched link), колонка действия скрыта на телефоне.
3. **Что купили / покупки клиента.** Таблицы → `.table-cards--compact`; тот же свёрнутый catalog-filter.
4. **Создание.** Поля на всю ширину; Excel/CSV в `.file-zone`; «Создать» в fixed-панели через `form="campaign-create-form"`; `disabled` после submit. Чекбокс локального списка в `.check-row` (тап-зона label ≥ 44 px).
5. **≥ 900 px.** Таблицы снова `display: table`, фильтры/пересчёт развёрнуты без summary, чипы статусов выглядят как текстовые ссылки.

Дополнительно: тег `{% pct %}` в `core/templatetags/ui.py` для доли на списке. i18n: `%(bought)s of %(total)s`, `Tap to choose Excel or CSV file`.

**row_limit:** во view `CLIENT_LIMIT = 500` (не менялся). Демо: 40 клиентов на кампанию (SMS/Telegram), `truncated` не срабатывает. На проде до 500 строк карточками — DOM тяжелее таблицы, но без второго экземпляра полей; 1700 на проде всё равно обрезаются view до 500 — карточный вид сам по себе view не ускоряет и не правился.

## Изменённые файлы

```text
 campaigns/templates/campaigns/_catalog_filter.html
 campaigns/templates/campaigns/client_purchases.html
 campaigns/templates/campaigns/create.html
 campaigns/templates/campaigns/detail.html
 campaigns/templates/campaigns/list.html
 campaigns/templates/campaigns/purchases.html
 core/templatetags/ui.py
 docs/mobile-first/STATUS.md
 docs/mobile-first/reports/stage-6.md
 locale/en/LC_MESSAGES/django.mo
 locale/en/LC_MESSAGES/django.po
 locale/ru/LC_MESSAGES/django.mo
 locale/ru/LC_MESSAGES/django.po
```

## Проверки

- `DB_HOST=localhost python manage.py test`: **93 tests OK** (39.1 s), в т.ч. `campaigns` 8 OK.
- Скриншоты: `python scripts/ui_snapshots.py --name stage6 --compare stage5` → `artifacts/ui/stage6/compare.html` (104 pages, exit 0). Перед прогоном `docker compose restart web`.
- Метрики из `report.json`, mobile 390 px, `demo_staff`:

| Страница | Гор. скролл (scrollWidth) до → после | Полей < 16px до → после | Элементов < 44px до → после |
|----------|--------------------------------------|-------------------------|------------------------------|
| campaigns | 494 → 390 | 0 → 0 | 0 → 0 |
| campaign_new | 390 → 390 | 0 → 0 | 1 → 1 |
| campaign_detail | 524 → 390 | 0 → 0 | 2 → 0 |
| campaign_purchases | 524 → 390 | 0 → 0 | 0 → 0 |
| campaign_client | 524 → 390 | 0 → 0 | 0 → 0 |

`campaign_new` tap=1: нативный `input#id_use_local_file` 18×18 (скрипт мерит input); label `.check-row` ≥ 44 px.

- Десктоп 1366 px: таблицы как раньше; у detail tap count вырос (имя купившего стало ссылкой + колонка «Состав заказа») — на телефоне колонка скрыта. Внешние CDN: 0.

## Изменения в тестах

нет

## Отклонения от RULES.md

нет (только шаблоны, `locale/`, новый тег отображения `pct`)

## Что проверить руками на телефоне

1. `/campaigns/` — тап по всей карточке → detail; «Новая кампания» всегда над нижним меню.
2. Detail — «Доля купивших» сверху; чипы All/Bought/… с подсветкой; тап по купившему → order items; фильтр групп свёрнут.
3. Create — зона файла крупная; Create внизу; повторный submit блокируется.
4. ≥ 900 px — таблица клиентов/списка, форма пересчёта и фильтр видны без раскрытия details.

## Не проверено

- Реальный телефон / Safari.
- Список на 500 строк (демо = 40); 1700 на проде не воспроизводили — только чтение `CLIENT_LIMIT`.
- `en` UI на телефоне глазами (строки переведены/скомпилированы).

## Найдено вне этапа

- `reconcile_docs` на 390 px по-прежнему h-scroll 980 без stub Granit (как на этапе 5) — не этап 6.
- Акции / promo picker — мелкие тап-зоны и формы (этап 7).
- На десктопе status-чипы снова компактные текстовые ссылки (< 44 px) — сознательно «как сейчас».

## Вопросы

нет

## Исправления по ревью

Код ревью: `b01707e` / tip `1821bdb` → rework (`reviews/stage-6.md`).

1. **Форма «Пересчитать» и catalog-filter на десктопе.** Убран CSS-хак `:not([open]) > … { display:… }` — содержимое закрытого `<details>` так не показать. Добавлен `campaigns/_desktop_details_open.html`: на ≥ 900 px JS через `matchMedia` ставит `open` у `.recalc-panel` и `.catalog-filter-panel` (как `sales/explorer.html`). Подключён на `detail`, `purchases`, `client_purchases`. На телефоне recalc свёрнут; catalog открыт только при `data-filter-active`.
2. **Проверка глазами (stage6b, desktop 1366, demo_staff):**
   - `artifacts/ui/stage6b/screenshots/campaign_detail__demo_staff__desktop.png` — видны «Пересчитать эту кампанию до» + дата + кнопка и селекты «Группа товара» / «Товар».
   - `artifacts/ui/stage6b/screenshots/campaign_purchases__demo_staff__desktop.png` — видны селекты фильтра каталога над таблицей.
   - `artifacts/ui/stage6b/screenshots/campaign_client__demo_staff__desktop.png` — видны селекты фильтра каталога над чеками.

Коммит фикса: `48db62a`. Проверки после фикса: `DB_HOST=localhost python manage.py test` — **93 OK**; `python scripts/ui_snapshots.py --name stage6b --compare stage6` → `artifacts/ui/stage6b/` (104 pages, exit 0). Мобильные campaign_* по-прежнему scrollWidth 390.
