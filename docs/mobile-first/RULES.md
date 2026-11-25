# Правила mobile-first (обязательны для всех этапов)

## 1. Что нельзя менять

- URL (`*/urls.py`), имена маршрутов, методы и `action` форм, `formaction`, параметры GET-фильтров
  (`scope`, `date_from`, `date_to`, `store`, `group`, `product`, `param`, `client`, `q`, `group_by`, `sort`, `status` и т.д.) —
  на них завязаны ссылки между экранами (`explorer_query`, `period_query`, `filter_query`) и закладки пользователей.
- Атрибуты `name`, `id`, `value` у полей и кнопок, все `data-*` и `hx-*` атрибуты.
- Python-логику: `views.py`, `models.py`, `analysis.py`, `matrix.py`, `charts.py`, `pricing.py`, `picker.py`,
  `reconcile*.py`, `etl/`, миграции. Расчёты и цифры не трогаем вообще.
  Разрешено: шаблоны, новый `static/`, `locale/*/LC_MESSAGES/django.po` (+ `compilemessages`), `core/templatetags/`
  (только новые фильтры/теги для отображения).
  Заранее согласованные исключения: `STATICFILES_DIRS` в `settings.py` (этап 1); view + URL `/more/` в `core` (этап 2).
  Любая другая правка Python — только после вопроса Ивану (статус `blocked`).
- Выгрузка Excel (`sales_matrix_xlsx`, `promo_example_xlsx`) и Django-админка — не трогаем.

Переносить элементы в разметке можно, удалять или переименовывать то, что выше, — нельзя.
Если кнопка переезжает в другое место (например, в липкую панель вне `<form>`), используй атрибут `form="<id формы>"`,
а не дубликат кнопки. Если для телефона нужна вторая разметка тех же данных (карточки вместо таблицы) — она не должна
содержать второй экземпляр полей формы (дубли `name` ломают отправку).

## 2. Контракт с JavaScript и HTMX

Список снят 24.11.2026 с коммита `18b8fd6`; на этапе 0 Cursor сверяет его с кодом и дополняет.

**`templates/base.html`** (фильтр `<select>` по вводу): класс `.select-filter`, атрибут `data-select`
(селектор `<select>` внутри той же формы); выбор языка: `select#language` с `onchange`, скрытое поле `next`,
форма `form.lang-switch`. То же переключение языка — в `templates/registration/auth_base.html`.

**`sales/explorer.html` + `sales/_explorer.html`:** оболочка `explorer.html` подключает HTMX 1.9.12 с unpkg;
частичный ответ при `request.htmx` — `_explorer.html`. `#sales-explorer` — цель `hx-target` и `outerHTML`-замена
всей обёртки (значит, обёртка и форма фильтров приходят заново после каждого изменения: состояние «фильтр
раскрыт» не переживёт swap без JS или `hx-preserve`);
`hx-trigger="change delay:200ms from:input:not(.select-filter), change delay:200ms from:select, submit"`;
`hx-push-url="true"`; `select[name=group]` c `onchange` сбрасывает `form.product`.

**`sales/matrix.html`, `matrix_group.html`, `matrix_sg.html`:** `#scope` (+ `#store` на `matrix_sg`) —
`onchange="this.form.submit()"` (полный POST, не HTMX).

**`campaigns/_catalog_filter.html`:** `form.catalog-filter`; `select[name=group]` сбрасывает product и submit;
`select[name=product]` — submit; скрытое `status` при фильтрации по статусу.

**`promos/create.html` (+ `promo_edit` рендерит тот же шаблон) + `promos/picker/*`:**
id: `promo-form`, `selected-body`, `selected-empty`, `selected-count`, `selected-clear`, `picker-granit`, `picker-site`,
`granit-filter`, `site-filter`, `granit-results`, `site-results`.
Классы: `dialog.picker`, `.picker-filter`, `.picker-results`, `.picker-status`, `.picker-add`, `.picker-add-all`,
`.picker-count`, `.picker-close`, `.picker-done`, `.tree`, `.tree-children`, `.tree-toggle`, `.tree-node`, `.tree-all`,
`.tree-spacer`, `li.open`, `.picker-table tr`, `input.pick`, `.check-all`, `tr.sel`, `tr.sel-group`, `.sel-remove`,
`.group-expand`, `.active`, `.load-more`, `tr.load-more`. JS переключает `active`, `open` — стили можно менять,
имена нельзя.
data: `data-open` (`picker-granit` / `picker-site`), `data-all-url`, `data-group`, `data-pk`, `data-name`,
`data-granit`, `data-site`.
Поля: `product_ids`, `group_ids` (скрытые, создаются JS в `tr.sel`), `q`, `group` (granit-фильтр), `category`
(site-фильтр; у узлов дерева сайта `data-group` всё равно = pk категории), `inactive`.
HTMX: `hx-target="next .tree-children"` — `ul.tree-children` должен оставаться **следующим соседом** `.tree-toggle`;
`hx-include="#granit-filter"` / `#site-filter`; триггер `refresh` у поиска дергает JS (`htmx.trigger(search, "refresh")`);
load-more в `_rows.html`: `hx-target="closest tr"`, `hx-swap="outerHTML"`, `hx-vals` с `offset`.
JS строит строку выбранного товара как `<tr>` с 4 `<td>` — если `sel-table` превращается в карточки, это делается CSS-ом
поверх той же структуры `tr/td`, а не сменой тегов (иначе правь и JS, и опиши в отчёте).

**`sales/matrix_edit.html`:** `[data-color-pick]` с парой `input[type=color]` + `input[type=text]` внутри;
формы `#sg-form-<pk>` и поля вне формы с `form="sg-form-<pk>"`; скрытые `action` (`update` / `move_up` /
`move_down` / `delete` / `create`), `sg_id`; `confirm()` при удалении; классы `.color-pick`, `.order-controls`,
`.btn-order`, `form.create`.

## 3. Тесты, которые завязаны на разметку

`python manage.py test` должен быть зелёным в конце каждого этапа (нужен Postgres: `docker compose up -d db`).
Строки, которые проверяют тесты (не менять смысл и точный вид):

- `sales/tests.py`: `"HORECA TBILISI</th>"` — проверяется и `assertContains`, и **`assertNotContains`**: имя магазина
  в заголовке матрицы появляется только при нужном scope. Если на телефоне добавляешь второй список магазинов,
  не используй для него `<th>` с именем магазина (иначе `assertNotContains` может стать ложным). Также
  `name="sg_id"`, `scope=all`, `source=invoice`, `source=realized`, `/sales/matrix/group/-1/`, `rc-badge bad`,
  `rc-badge open`, `Месяц не закрыт`, числа вида `29,67`, `DGVDT 10`, `coffee kg`, подсказка остатков
  `Stock is remainder as of the period end date for the selected store filter`, URL месяцев/документов сверки
  (`sales_reconcile_month`, `sales_reconcile_docs`).
- `promos/tests.py`: `<svg`, **`<svg class="chart"`** (точная строка — если добавляешь классы, первым оставь `chart`
  и проверь тест; на списке без графиков — `assertNotContains`), `name="group_ids"`, `name="product_ids" value="…"`,
  `value="<pk>"`, `disabled`, тексты `product missing in Woo sync`, `no site link`, `Live` / `Old` (список акций),
  фикстуры пикера (`2154`, `1702`, `904`, `6219`, имена вроде `Coffee machines` / `ECAM450` / `Site orphan`),
  ссылка на `promo_charts`, отсутствие ссылки `promo_sync_catalog` для не-staff.
- `core/tests.py`: ссылка на `register` есть/нет в зависимости от `ALLOW_REGISTRATION`.

Если тест падает из-за изменившейся разметки — не правь его молча. Опиши в отчёте: какой тест, что проверял,
почему изменение UI правильное, как поправлен тест. Тесты на расчёты, сверку и права не менять.

## 4. CSS

- После этапа 1 общие стили — в `static/css/app.css` (подключён в `base.html` через `{% static %}`).
  В `{% block extra_css %}` шаблона остаётся только специфичное для экрана; дубли `.btn`, `.hint`, `table`, `.stats`,
  `.empty` переносить в общий файл по мере работы с экраном.
- Mobile-first: базовые стили — для телефона; расширения только `@media (min-width: 600px | 900px | 1200px)`.
  `max-width` медиазапросов не добавлять (кроме `@media print`).
- Цвета, отступы, радиусы, высоты — через CSS-переменные в `:root` (после этапа 1). Бренд — текущий `#667eea`/`#4c51bf`.
- На 390 px нет горизонтального скролла **страницы**. Широкие таблицы — паттерн `.table-cards` (этап 3) или
  скролл **внутри** обёртки `.scroll-x` с видимым краем/тенью (только для матриц, где карточки не подходят).
- Тап-зоны ≥ 44×44 px. Шрифт `input`, `select`, `textarea` ≥ 16 px на телефоне.
- Липкие панели и нижнее меню учитывают `env(safe-area-inset-bottom)`; контент под ними не прячется.
- Числа: `font-variant-numeric: tabular-nums`, выравнивание вправо; длинные названия товаров переносятся, а не режутся,
  если это единственный идентификатор строки.
- Десктоп (≥ 900 px) не должен стать хуже.

## 5. Тексты и языки

- Все видимые тексты — через `{% trans %}` / `{% blocktrans %}`, ключи на английском (как сейчас), переводы — в
  `locale/ru/LC_MESSAGES/django.po` (en — ключ = текст). После правок: `makemessages -l ru -l en`, перевести новые
  `msgid`, `compilemessages`; `.mo` коммитится (как сейчас в репозитории).
- Русские подписи длиннее английских: проверять нижнее меню и чипы на `ru` (основной язык) и на `en`.
- Данные ERP (названия товаров, магазинов, групп) не переводим и не сокращаем на сервере — только CSS (перенос/обрезка с `title`).

## 6. Git

- Одна ветка на этап, от актуального `main`. Имя — в промпте этапа.
- Коммиты небольшие, понятные сообщения.
- В `main` не мержить и `main` не пушить: push в `main` = сборка прод-образа.
- `artifacts/` (скриншоты) не коммитить. `.env` не трогать и не коммитить.

## 7. Паттерны для новых экранов

Копируй эти приёмы; не изобретай второй каркас или вторую карточку.

### Каркас страницы (`page_title`, `back_url`)

В шаблоне экрана задай блоки базового `templates/base.html`. На телефоне заголовок в плашке,
`h1`/`.page-back` скрыты CSS (≥ 900 px — наоборот).

```html
{% block page_title %}{% trans "Screen name" %}{% endblock %}
{% block back_url %}{% url 'parent_list' %}{% endblock %}
```

Иконки — `{% include "partials/icon.html" with name="sales" %}` (`currentColor`, без внешних наборов).

### Свёрнутая строка фильтра

```html
<details class="filter-panel" id="…"{% if filter_active %} open data-filter-active{% endif %}>
  <summary class="filter-summary"><span class="filter-summary-text">01.11 – 24.11 · …</span></summary>
  <form>…поля…</form>
</details>
```

На телефоне свёрнуто (или открыто, если фильтр активен). На ≥ 900 px — см. следующий пункт.

### `<details>`: свёрнут на телефоне / раскрыт на десктопе — только через `open` из JS

Содержимое закрытого `<details>` **нельзя** показать CSS (`:not([open]) > … { display:… }` не работает —
браузер прячет слот до применения стилей ребёнка). Образец: `sales/explorer.html`,
`campaigns/_desktop_details_open.html`.

```js
var MQ = window.matchMedia("(min-width: 900px)");
function sync() {
  document.querySelectorAll("details.filter-panel, details.recalc-panel").forEach(function (el) {
    if (MQ.matches) { el.open = true; return; }
    if (!el.hasAttribute("data-filter-active")) el.open = false;
  });
}
MQ.addEventListener("change", sync);
sync();
```

На ≥ 900 px summary обычно `display: none`.

### KPI-плитки

```html
<div class="stats-tiles">
  <div class="stat stat-primary"><span>{% trans "Amount" %}</span><strong>…</strong></div>
  <div class="stat"><span>…</span><strong>…</strong></div>
  <div class="stat"><span>…</span><strong>…</strong></div>
</div>
```

Телефон: CSS grid 2 колонки; главная метрика — `grid-column: 1 / -1` первой. ≥ 900 px — ряд/сетка как раньше.

### `.table-cards` и `--compact`

Одна `<table>`: на телефоне карточки, на ≥ 900 px обычная таблица (`static/css/app.css`).

```html
<table class="table-cards table-cards--compact">
  <thead>…</thead>
  <tbody>
    <tr>
      <td class="tc-primary" data-label="{% trans 'Name' %}"><a href="…">Name</a></td>
      <td class="tc-meta" data-label="{% trans 'Period' %}">…</td>
      <td class="num tc-amount" data-label="{% trans 'Amount' %}">…</td>
      <td class="tc-action"><!-- скрыть на телефоне, если есть stretched link --></td>
    </tr>
  </tbody>
</table>
```

**Растянутая ссылка (без отдельной кнопки):** карточка `position: relative`; у основной ссылки
`.tc-primary a::after { position: absolute; inset: 0; }` — тап по всей карточке ≥ 44 px.
Колонку `.tc-action` на телефоне скрыть; на ≥ 900 px — как раньше. Цель: 4–5 строк на 390×844.

Если JS строит `<tr>`/`<td>` (пикер акций) — карточки только CSS поверх той же разметки, теги не менять.

### `.scroll-x`

Широкая матрица или SVG-график: скролл **внутри** обёртки, не страницы.

```html
<div class="scroll-x">
  <table class="matrix">…</table>
  <!-- или --><svg class="chart" style="min-width:640px">…</svg>
</div>
```

Класс `chart` у SVG оставляй первым (`promos/tests.py` ищет `"<svg class=\"chart\""`).

### Липкая панель действий

На телефоне основное действие над нижним меню; на ≥ 900 px — кнопка в форме/`page-head`, панель `display: none`.
Кнопка вне `<form>` — через `form="<id>"` (не дублировать поля).

```html
<div class="container has-sticky-action">
  <form id="entity-form">…</form>
  <div class="sticky-action">
    <button class="btn" type="submit" form="entity-form">{% trans "Save" %}</button>
  </div>
</div>
```

Защита от двойной отправки: на `submit` ставь `disabled` на все кнопки этой формы.

### Чипы со скроллом

```html
<div class="status-chips"><!-- или .promo-tabs / .explorer-chips -->
  <a href="?status=all" class="is-active">…</a>
  <a href="?status=bought">…</a>
</div>
```

`display: flex; overflow-x: auto`; чипы `flex: 0 0 auto; min-height: var(--tap)`. Активный — класс + стили,
не другой URL-контракт.
