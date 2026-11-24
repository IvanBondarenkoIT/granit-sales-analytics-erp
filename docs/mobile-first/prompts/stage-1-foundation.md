# Этап 1. Фундамент

Ветка: `feature/mobile-1-foundation`. Файлы: `templates/base.html`, `templates/registration/auth_base.html`, новый
`static/`, `granitanalytics/settings.py` (только `STATICFILES_DIRS`), атрибуты полей в шаблонах и `*/forms.py`
(только `widget.attrs`: `type`, `inputmode`, `autocomplete` и т.п. — это не логика).
Раскладку экранов в этом этапе не меняем.

## Задача

1. **Общий CSS.** Создай `static/css/app.css`, добавь `STATICFILES_DIRS = [BASE_DIR / "static"]`, подключи в `base.html`
   и `auth_base.html` через `{% static 'css/app.css' %}` (whitenoise уже настроен — проверь `collectstatic` в Docker-сборке).
   Перенеси туда стили из `<style>` `base.html` и общие компоненты, повторяющиеся в шаблонах: `.btn`, `.btn-secondary`,
   `.btn-link`, `.btn-danger`, `.hint`, `.muted`, `.empty`, `.stats`/`.stat`, базовые `table/th/td/.num/tfoot`, `.ok/.bad/.up/.down`.
   Сведи их к одному виду (сейчас `.btn` в 6 вариантах). Из шаблонов дубли удали, специфичное оставь.
   CSS-переменные в `:root`: цвета бренда и статусов, `--gap`, `--radius`, `--tap: 44px`, `--bar-h: 52px`, `--nav-h`.
   Базовые стили — для телефона, `@media (min-width: 600/900/1200px)` — расширения. На 1366 px вид не должен заметно
   поменяться (кроме выравнивания разнобоя кнопок) — сравни скриншотами.
2. **Без CDN.** `static/vendor/htmx-1.9.12.min.js` (та же версия, не обновлять — 2.x меняет поведение), подключить в
   `base.html` один раз для всех страниц; убрать `<script src="https://unpkg.com/...">` из `sales/explorer.html` и
   `promos/create.html`. Если инлайн-JS в `base.html` разрастается — вынести в `static/js/app.js` без изменения поведения.
3. **Поля.** На телефоне `font-size` у `input`, `select`, `textarea` ≥ 16 px (во всех шаблонах, включая `.toolbar`,
   `.picker-filter`, `.lang-switch`, `.sel-table`, `matrix_edit`). Высота полей и кнопок ≥ 44 px. Поля без `type` —
   явный `type="text"` (в `matrix_edit` и др.).
4. **Клавиатуры.** Суммы/цены/дни — `inputmode="decimal"` или `numeric`; «Client ID» — `inputmode="numeric"`; поиск —
   `type="search" enterkeyhint="search"`; ключ супергруппы — `autocapitalize="off" spellcheck="false"`; логин —
   `autocapitalize="off"`.
5. **Тап-зоны.** `.btn-link`, ссылки-действия, чекбоксы с лейблом, стрелки ↑↓, выбор языка: ≥ 44 px на телефоне
   (`min-height`/`padding`, визуально не раздувая).
6. **Safe-area и PWA-минимум.** `viewport-fit=cover`; `<meta name="theme-color" content="#667eea">`;
   `static/manifest.webmanifest` (имя, иконки 192/512 — сгенерируй простые из бренда, `display: standalone`, `start_url: /`).
   Service worker не добавлять. Переменная для нижнего отступа под меню (используется на этапе 2).
7. `container` на телефоне: `padding: 1rem`; размеры `h1/h2` в общем CSS.

## Проверки

`python manage.py test`; `python manage.py collectstatic --noinput` без ошибок;
`python scripts/ui_snapshots.py --name stage1 --compare baseline`.
Цель: полей < 16 px = 0 на всех страницах 390 px; внешних запросов = 0; на 1366 px визуально без существенных изменений.
