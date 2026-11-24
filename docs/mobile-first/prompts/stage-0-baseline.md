# Этап 0. Демо-данные, скрипт скриншотов и сверка контракта

Ветка: `feature/mobile-0-baseline`. UI в этом этапе не меняется.

## Задача

1. **Сверка контракта.** Пройди весь JS (инлайн-скрипты в `templates/base.html`, `promos/templates/promos/create.html`,
   `sales/templates/sales/matrix_edit.html` и любые другие `<script>`, `onchange`, `onsubmit`) и все `hx-*` в шаблонах,
   сверь с разделом 2 `RULES.md`. Пройди `*/tests.py` и сверь раздел 3 (строки разметки в `assertContains/NotContains`).
   Чего не хватает — допиши в `RULES.md`; лишнее — оставь, отметь в отчёте. Других правок в `RULES.md` не делай.

2. **Демо-данные для UI.** Management command `core/management/commands/seed_ui_demo.py` (новый файл — это
   разрешённое исключение по Python, только для локальной разработки): детерминированно (фиксированный seed) создаёт
   в текущей БД через модели — 4–5 магазинов (включая `HORECA TBILISI` и магазин с длинным названием), группы и
   товары (с длинными названиями, весовые и штучные), параметр «продукция», 300–500 строк продаж за 3 месяца
   (чеки, реализации, инвойсы — все `source`), остатки, 3–4 супергруппы с цветами, снимок сверки за месяц со статусами
   ok / open / bad, 2 кампании (SMS и Telegram, 30–50 клиентов, часть купила), 3 акции (активная, прошедшая, без анализа)
   с ценами и посчитанным анализом для графиков. Используй, где можно, существующие `seed_promo_demo`, `seed_supergroups`
   и фабрики из `*/tests.py`. Команда отказывается работать, если `DEBUG=False` или БД не пустая (флаг `--force` для
   пересоздания). Пользователи: `demo_staff` (is_staff) и `demo_user` (обычный), пароль из аргумента/дефолт для локали.

3. **Скрипт `scripts/ui_snapshots.py`** (Playwright, Chromium):
   - работает с запущенным локальным приложением (`--base-url`, по умолчанию `http://localhost:8000`) на БД после
     `seed_ui_demo`; в README раздела — как поднять (`docker compose up -d`, `migrate`, `seed_ui_demo`). Прод-БД и
     `.env` с прод-доступом не трогать;
   - логинится `demo_staff` и `demo_user`, снимает full-page скриншоты всех страниц, доступных пользователю:
     login, register, `/`, `/sales/` (дефолт и с `group_by=receipt`, `scope=all`), чек, `/sales/matrix/`, супергруппа,
     группа, `/sales/matrix/edit/`, `/sales/reconcile/`, месяц, документы магазина, `/campaigns/`, карточка кампании,
     «что купили», покупки клиента, `/campaigns/new/`, `/promos/`, карточка, графики, `/promos/new/`, редактирование,
     и **открытый пикер** (клик по `[data-open=picker-granit]`, выбор группы) — отдельным скриншотом;
   - два размера: 390×844 (`is_mobile=True`, `has_touch=True`, `device_scale_factor=2`) и 1366×900;
   - `--locale en` (переключает язык через POST `/i18n/setlang/`); по умолчанию `ru`;
   - для каждой страницы пишет в `report.json`: `scrollWidth` vs `innerWidth`; интерактивные элементы
     (a, button, input, select, textarea, summary, label с чекбоксом) высотой < 44 px — число и первые 10 с селектором;
     число полей с font-size < 16 px; ошибки консоли; упавшие запросы; запросы к внешним доменам;
   - сохраняет в `artifacts/ui/<name>/` (`--name`, по умолчанию имя git-ветки); добавь `artifacts/` в `.gitignore`;
   - `--compare <другой прогон>` собирает `artifacts/ui/<name>/compare.html`: по каждой странице и размеру «до» и
     «после» рядом + таблица метрик с подсветкой ухудшений;
   - `playwright` — в новый `requirements-dev.txt` (в Docker-образ не попадает); понятная ошибка с командой установки,
     если Playwright/Chromium нет.

4. Прогони `python manage.py seed_ui_demo`, `python scripts/ui_snapshots.py --name baseline` и `python manage.py test`.

5. В `README.md` проекта — раздел «UI-скриншоты» в 3–5 строк.

## Отчёт

`docs/mobile-first/reports/stage-0.md` по шаблону. В «Проверках» — сводка `report.json` baseline по всем страницам
на 390 px (страница, scrollWidth, полей < 16px, элементов < 44px, ошибки консоли, внешние запросы).
`AUDIT.md` составлен по коду, без браузера: напиши, что подтвердилось, что нет, что нашлось нового.
