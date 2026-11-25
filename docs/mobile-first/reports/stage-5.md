# Отчёт: этап 5 — Сверка с Гранитом

- Ветка: `feature/mobile-5-reconcile`
- Коммит: `1d9870a`
- Дата: 2026-11-25
- Итог: готово к ревью

## Что сделано

1. **Обзор `/sales/reconcile/`.** Таблица месяцев заменена на карточки `.rc-month`: заголовок-ссылка на `sales_reconcile_month` + `_reconcile_status` (`pill` / те же msgid), строка «Гранит · наши · разница», мета Goods/Services/Leftover. Флаги — `<details class="rc-flags-toggle">` со счётчиком `{{ n }} flag(s)`. Длинный `.rc-hint` — одна строка + ▾ (`rc-collapse`). Pivot «Services by month» — в `.scroll-x`. Кнопка Recalculate (staff) — `.btn` / `--tap`.
2. **Месяц.** Hint и `rc-note` свёрнуты тем же приёмом. Таблица магазинов → `.table-cards.rc-store-cards`: ссылка магазина в `.tc-primary` с растянутым `::after`, Diff крупно справа (`.tc-amount`), ниже 2×2 Granit / Ours goods / Ours services / Not realized. Goods/Services/Leftover/Status/склады — в «Подробнее» на телефоне; на ≥ 900 px — исходные колонки + `.rc-wh-desktop` под именем. Services / Other types — `.scroll-x`.
3. **Документы.** `.table-cards--compact.rc-doc-cards`: документ + DGVDT, дата, Granit / Ours / Diff на телефоне; остальное в «Подробнее». Порядок колонок на десктопе как до этапа.
4. **Stub proxy.** `scripts/stub_granit_proxy.py` — `GET /api/health`, `POST /api/query` (STORGRPREF / STORLIST без коллизии с KIND_GROUP 33/41/55/133, ответы `AS SZID` с DGVDT). Только для локального прогона: `PROXY_API_URL` / `PROXY_API_TOKEN=local-stub` (host или `host.docker.internal` из Docker). Python приложения не менялся. У `reconcile_docs` в `ui_snapshots.py` снят `expected_error`.
5. **i18n.** «More details» → «Подробнее»; `%(n)s flag(s)` → «флаг/флага/флагов». `makemessages` + `compilemessages`.

## Изменённые файлы

```text
 docs/mobile-first/STATUS.md
 docs/mobile-first/reports/stage-5.md
 locale/en/LC_MESSAGES/django.mo
 locale/en/LC_MESSAGES/django.po
 locale/ru/LC_MESSAGES/django.mo
 locale/ru/LC_MESSAGES/django.po
 sales/templates/sales/_reconcile_style.html
 sales/templates/sales/reconcile.html
 sales/templates/sales/reconcile_docs.html
 sales/templates/sales/reconcile_month.html
 scripts/stub_granit_proxy.py
 scripts/ui_snapshots.py
```

## Проверки

- `DB_HOST=localhost python manage.py test`: **93 tests OK** (37.9 s). `ReconcilePageTests` (4) — отдельно зелёные: URL месяцев/docs, `Месяц не закрыт`, `DGVDT 10`, staff refresh.
- Скриншоты: stub на `:8765` + web с `PROXY_API_URL=http://host.docker.internal:8765` (временный compose-override, не в репо) → `python scripts/ui_snapshots.py --name stage5 --compare stage4` → `artifacts/ui/stage5/compare.html` (104 pages, exit 0). После прогона web пересоздан без stub-override.
- Метрики из `report.json`, mobile 390 px, `demo_staff`:

| Страница | Гор. скролл (scrollWidth) до → после | Полей < 16px до → после | Элементов < 44px до → после |
|----------|--------------------------------------|-------------------------|------------------------------|
| reconcile | 1008 → 390 | 0 → 0 | 3 → 0 |
| reconcile_month | 1142 → 390 | 0 → 0 | 3 → 0 |
| reconcile_docs | 980 → 390 | 2 → 0 | 6 → 0 |

Цель этапа: `scrollWidth = 390` на всех трёх — выполнена. Docs с stub отдаёт 200 и содержит `DGVDT`.

- Десктоп 1366 px: таблицы магазинов/документов снова `display: table`, склады под именем магазина, флаги списками без summary. Внешние CDN: 0.

## Изменения в тестах

нет

## Отклонения от RULES.md

нет (Python views/`etl` не трогались; новый скрипт только в `scripts/`)

## Что проверить руками на телефоне

1. `/sales/reconcile/` — карточки месяцев, тап по названию → месяц; раскрытие флагов; Recalculate ≥ 44 px (staff).
2. Месяц — тап по всей карточке магазина → документы; Diff читается первым; «Подробнее» показывает склады и leftover.
3. Документы (со stub) — компактные карточки, `DGVDT N` виден, нет горизонтального скролла страницы.
4. ≥ 900 px — таблицы как раньше, подсказки полностью видны.

## Не проверено

- Реальный телефон / Safari.
- Реальный Granit proxy (только stub).
- `en` UI на телефоне глазами (строки переведены/скомпилированы).
- POST Recalculate против stub (stub отвечает на часть SQL refresh, полный nightly ETL не гонялся).

## Найдено вне этапа

- Кампании на 390 px по-прежнему с h-scroll (`campaigns` 494, detail/purchases/client 524) — этап 6.
- Без stub / с пустым `PROXY_API_URL` страница docs — 200 + баннер «Granit is not reachable» (ProxyApiError). 500 возможен, если живой proxy отдаёт warehouse ID = KIND_GROUP (ValueError в `warehouse_store_routes`, view не ловит) — stub как раз обходит это; чинить except во view вне этапа.

## Вопросы

нет
