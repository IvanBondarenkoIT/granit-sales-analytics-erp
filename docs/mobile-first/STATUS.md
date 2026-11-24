# Статус этапов

Статусы: `todo` · `in_progress` · `review` · `rework` · `blocked` · `done`. Порядок работы — в `README.md`.

| # | Этап | Промпт | Ветка | Статус | Обновлено | Последний коммит | Отчёт | Ревью |
|---|------|--------|-------|--------|-----------|------------------|-------|-------|
| 0 | Демо-данные, скрипт скриншотов, сверка контракта | [stage-0](prompts/stage-0-baseline.md) | feature/mobile-0-baseline | review | 2026-11-24 | *(см. отчёт)* | [stage-0.md](reports/stage-0.md) | |
| 1 | Фундамент: static/app.css, htmx локально, поля 16px, тап-зоны, safe-area | [stage-1](prompts/stage-1-foundation.md) | feature/mobile-1-foundation | todo | | | | |
| 2 | Каркас: плашка, нижнее меню, «Ещё», главная | [stage-2](prompts/stage-2-shell.md) | feature/mobile-2-shell | todo | | | | |
| 3 | Обозреватель продаж и чек, паттерн `.table-cards` | [stage-3](prompts/stage-3-explorer.md) | feature/mobile-3-explorer | todo | | | | |
| 4 | Супергруппы (матрица, детализация, редактор) | [stage-4](prompts/stage-4-matrix.md) | feature/mobile-4-matrix | todo | | | | |
| 5 | Сверка с Гранитом | [stage-5](prompts/stage-5-reconcile.md) | feature/mobile-5-reconcile | todo | | | | |
| 6 | Кампании | [stage-6](prompts/stage-6-campaigns.md) | feature/mobile-6-campaigns | todo | | | | |
| 7 | Акции (карточка, графики, форма, пикер), итоговая проверка | [stage-7](prompts/stage-7-promos.md) | feature/mobile-7-promos | todo | | | | |

Этапы 0 → 1 → 2 → 3 строго по порядку (на 3 появляется `.table-cards`). 4–7 можно переставлять, но каждый начинается
от `main` с уже смерженными предыдущими. Итоговая проверка — в последнем выполненном этапе.

## Заметки

<!-- Cursor и Claude добавляют сюда короткие заметки, которые касаются нескольких этапов. Новые сверху. -->

- 2026-11-24 этап 0: baseline в `artifacts/ui/baseline/` (gitignored). Документы сверки магазина дают 500 без Granit proxy — учесть на этапе 5 / в seed, если понадобятся скриншоты docs.
