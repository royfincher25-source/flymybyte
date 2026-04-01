# Отказ от Bootstrap — Дизайн

**Дата:** 2026-04-01

**Цель:** Полный отказ от Bootstrap 5.3 CDN + Bootstrap Icons 1.11 CDN. Замена на кастомный CSS (~25 KB) + иконочный шрифт WOFF2 (~10 KB) + vanilla JS (~80 строк).

**Архитектура:** Подход B — кастомный иконочный шрифт (Lucide SVG → WOFF2 через fantasticon) + семантическая CSS компонентная система (BEM-подобный стиль) + CSS Grid вместо Bootstrap grid + минимальный vanilla JS для модалок/тостов.

**Ожидаемый результат:** ~35 KB вместо ~250 KB Bootstrap CDN. 0 внешних зависимостей. Работает оффлайн.

---

## Секция 1: Иконочный шрифт FlyMyByte Icons

### Источник

63 иконки из Lucide (MIT лицензия). Все иконки в формате SVG 24x24.

### Генерация

Инструмент: `fantasticon` (npm). Вход: папка SVG. Выход: WOFF2 + CSS.

```
src/web_ui/static/icons/svg/     # 63 SVG файла
       ↓ fantasticon
src/web_ui/static/fonts/
  ├── flymybyte-icons.woff2      # ~10 KB
  └── flymybyte-icons.css        # @font-face + .fm-* классы
```

### Формат классов

```css
.fm { display: inline-block; font-family: 'FlyMyByte Icons'; }
.fm-sm { font-size: 0.875em; }
.fm-lg { font-size: 1.25em; }
.fm-xl { font-size: 1.5em; }
.fm-arrow-left::before { content: "\e001"; }
/* ... 63 иконки */
```

### Миграция иконок (63 unique → 63 fm-*)

| Bootstrap Icon | Lucide | New class | Вхождений |
|---|---|---|---|
| `bi-arrow-left` | `arrow-left` | `.fm-arrow-left` | 17 |
| `bi-gear` | `settings` | `.fm-settings` | 11 |
| `bi-info-circle` | `info` | `.fm-info` | 14 |
| `bi-circle-fill` | `circle` | `.fm-circle-fill` | 14 |
| `bi-download` | `download` | `.fm-download` | 9 |
| `bi-exclamation-triangle` | `triangle-alert` | `.fm-triangle-alert` | 8 |
| `bi-check-circle` | `circle-check` | `.fm-circle-check` | 7 |
| `bi-folder` | `folder` | `.fm-folder` | 9 |
| `bi-file-text` | `file-text` | `.fm-file-text` | 9 |
| `bi-shield-check` | `shield-check` | `.fm-shield-check` | 6 |
| `bi-key` | `key` | `.fm-key` | 5 |
| `bi-list-check` | `list-checks` | `.fm-list-checks` | 4 |
| `bi-lightning-charge-fill` | `zap` | `.fm-zap-fill` | 4 |
| `bi-graph-up` | `trending-up` | `.fm-trending-up` | 3 |
| `bi-list-ul` | `list` | `.fm-list` | 3 |
| `bi-journal-text` | `book-text` | `.fm-book-text` | 4 |
| `bi-activity` | `activity` | `.fm-activity` | 2 |
| `bi-hdd-network` | `network` | `.fm-network` | 2 |
| `bi-globe` | `globe` | `.fm-globe` | 2 |
| `bi-globe2` | `globe-2` | `.fm-globe-2` | 2 |
| `bi-collection` | `collection` | `.fm-collection` | 2 |
| `bi-search` | `search` | `.fm-search` | 2 |
| `bi-memory` | `memory-stick` | `.fm-memory-stick` | 2 |
| `bi-cpu` | `cpu` | `.fm-cpu` | 1 |
| `bi-database` | `database` | `.fm-database` | 1 |
| `bi-wifi` | `wifi` | `.fm-wifi` | 1 |
| `bi-lightning` | `lightning` | `.fm-lightning` | 1 |
| `bi-router` | `router` | `.fm-router` | 1 |
| `bi-hdd` | `hard-drive` | `.fm-hard-drive` | 3 |
| `bi-check-circle-fill` | `circle-check` | `.fm-circle-check-fill` | 2 |
| `bi-x-circle-fill` | `circle-x` | `.fm-circle-x-fill` | 1 |
| `bi-exclamation-triangle-fill` | `triangle-alert` | `.fm-triangle-alert-fill` | 1 |
| `bi-arrow-up-circle-fill` | `arrow-up-circle` | `.fm-arrow-up-circle-fill` | 1 |
| `bi-pc-display` | `monitor` | `.fm-monitor` | 1 |
| `bi-cloud-download` | `cloud-download` | `.fm-cloud-download` | 1 |
| `bi-shield-lock` | `shield-lock` | `.fm-shield-lock` | 1 |
| `bi-folder2-open` | `folder-open` | `.fm-folder-open` | 2 |
| `bi-list` | `menu` | `.fm-menu` | 1 |
| `bi-x-circle` | `circle-x` | `.fm-circle-x` | 1 |
| `bi-lock` | `lock` | `.fm-lock` | 1 |
| `bi-box-arrow-in-right` | `log-in` | `.fm-log-in` | 1 |
| `bi-box-arrow-right` | `log-out` | `.fm-log-out` | 1 |
| `bi-github` | `github` | `.fm-github` | 1 |
| `bi-tag` | `tag` | `.fm-tag` | 1 |
| `bi-menu-app` | `layout-grid` | `.fm-layout-grid` | 1 |
| `bi-play` | `play` | `.fm-play` | 3 |
| `bi-trash` | `trash-2` | `.fm-trash-2` | 3 |
| `bi-x-lg` | `x` | `.fm-x` | 3 |
| `bi-terminal` | `terminal` | `.fm-terminal` | 1 |
| `bi-check-lg` | `check` | `.fm-check` | 2 |
| `bi-question-circle` | `circle-help` | `.fm-circle-help` | 2 |
| `bi-plus-lg` | `plus` | `.fm-plus` | 2 |
| `bi-dash-lg` | `minus` | `.fm-minus` | 2 |
| `bi-eye` | `eye` | `.fm-eye` | 1 |
| `bi-pause` | `pause` | `.fm-pause` | 1 |
| `bi-play-fill` | `play` | `.fm-play-fill` | 1 |
| `bi-stop-fill` | `square` | `.fm-square-fill` | 1 |
| `bi-save` | `save` | `.fm-save` | 1 |
| `bi-list-task` | `list-todo` | `.fm-list-todo` | 1 |
| `bi-bug` | `bug` | `.fm-bug` | 1 |
| `bi-inbox` | `inbox` | `.fm-inbox` | 1 |
| `bi-arrow-clockwise` | `refresh-cw` | `.fm-refresh-cw` | 10 |
| `bi-arrow-repeat` | `repeat` | `.fm-repeat` | 6 |

---

## Секция 2: CSS компонентная система

### Именование

BEM-подобный стиль: `.block`, `.block__element`, `.block--modifier`.

### Компоненты

| Bootstrap | Новый класс | Уже в style.css |
|---|---|---|
| `card`, `card-body`, `card-header` | `.card`, `.card__body`, `.card__header` | Да (частично) |
| `btn`, `btn-primary`, `btn-danger`... | `.btn`, `.btn--primary`, `.btn--danger`... | Да (частично) |
| `form-control`, `form-label` | `.input`, `.label` | Да (частично) |
| `alert`, `alert-success`... | `.alert`, `.alert--success`... | Нет |
| `table`, `table-hover` | `.table`, `.table--hover` | Нет |
| `badge` | `.badge` | Нет |
| `progress`, `progress-bar` | `.progress`, `.progress__bar` | Нет |
| `navbar`, `nav-link` | `.navbar`, `.nav-link` | Да (частично) |
| `list-group`, `list-group-item` | `.list`, `.list__item` | Нет |
| `modal` | `.modal` | Нет |
| `toast` | `.toast` | Нет |
| `spinner-border` | `.spinner` | Нет |
| `form-switch` | `.switch` | Нет |

### Цветовая система

Сохраняем текущие `:root` переменные из style.css (бирюзовая тема).

---

## Секция 3: Grid, Utilities, JS

### Grid (CSS Grid)

```css
.container { max-width: 1200px; margin: 0 auto; padding: 0 1rem; }
.row { display: grid; gap: 1rem; }
.row--2col { grid-template-columns: repeat(2, 1fr); }
.row--3col { grid-template-columns: repeat(3, 1fr); }
.row--4col { grid-template-columns: repeat(4, 1fr); }
.row--auto { grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }
/* Mobile: все в 1 колонку */
```

### Utilities (~40 классов)

`d-flex`, `d-none`, `d-grid`, `flex-between`, `flex-center`, `gap-1/2/3`,
`mt-2/3/4`, `mb-2/3/4`, `p-3`, `text-center`, `text-muted`,
`text-success/danger/warning/info`, `fw-bold`, `w-100`, `h-100`,
`shadow-sm`, `rounded`, `visually-hidden`.

### JS (~80 строк)

- Модалка: open/close/backdrop (~30 строк)
- Тосты: динамическое создание + автоудаление (~25 строк)
- Form spinner: disable button + show spinner on submit (~15 строк)
- Loading overlay: show/hide (~10 строк)

---

## Фазы реализации

| Фаза | Задача | Объём |
|------|--------|-------|
| 1 | 63 SVG иконки + генерация WOFF2 | 2-3 дня |
| 2 | Переписать style.css: компоненты + utilities + grid | 5-7 дней |
| 3 | Заменить все классы в 19 шаблонах | 5-7 дней |
| 4 | Vanilla JS (modal, toast, spinner) | 1-2 дня |
| 5 | Убрать Bootstrap CDN, тестирование | 1-2 дня |

**Итого:** 14-21 дней. Результат: ~35 KB вместо ~250 KB.
