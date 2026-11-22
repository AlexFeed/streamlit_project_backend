[English](DASHBOARD_SCHEMA_V2.md) | **Русский**

# Dashboard Schema v2 — backend contract

Backend принимает декларативную схему из React-редактора, валидирует её через Pydantic v2 (`app/schemas/dashboard.py`) и использует как единый источник как для встроенного предпросмотра на движке **Streamlit** (`/preview`), так и для экспортируемого `app.py`.

## Корневая структура схемы (`DashboardSchema`)

| Поле | Тип / ограничения | По умолчанию | Описание |
| --- | --- | --- | --- |
| `version` | `1 \| 2` | `2` | Версия контракта схемы |
| `dashboard` | `{ title: str, grid: { columns: 12 } }` | `title: "Untitled dashboard"` | Метаданные дашборда и 12-колоночной сетки |
| `pages` | `list[DashboardPage]` (`min_length=1`) | `[{"id": "page-main", "title": "Главная", "order": 1}]` | Список страниц дашборда (`id`, `title`, `order >= 1`; `id` уникальны) |
| `dataSources` | `list[DataSource]` (`min_length=1`) | — | Источники данных: `type="backend_dataset"`, `datasetId`, `name`, `format`, `delimiter`, `encoding`, `sheetName`, `fields` |
| `filters` | `list[SelectboxFilter \| DataControlFilter]` | `[]` | Глобальные фильтры и элементы управления данными |
| `views` | `list[DashboardView]` | `[]` | Визуальные компоненты, текстовые блоки, ссылки на страницы и контейнеры |

### Правила целостности схемы

- `id` компонентов уникальны в пределах `filters`, в пределах `views` и по всему дашборду в целом.
- `pageId` каждого компонента должен ссылаться на существующую страницу в `pages`.
- `targetPageId` у `page_link` должен ссылаться на существующую страницу в `pages`.
- Контейнеры `layout_group` и `tab_group` не могут быть вложены друг в друга (`parentId` для них запрещён).
- Если у компонента указан `parentId`, родитель должен быть `layout_group` или `tab_group` на той же странице (`pageId`).

## Общие поля компонентов (`ComponentBase`)

Все модели компонентов настроены с `extra="forbid"` и `populate_by_name=True` (принимаются `camelCase`-алиасы и `snake_case`-имена, ответ возвращается в `camelCase`).

- **Идентификация и привязка:** `id` (`str`), `order` (`int >= 1`), `title` (`str = ""`), `pageId` (`str = "page-main"`), `datasetId` (`str | null = null`), `parentId` (`str | null = null`), `tabId` (`str | null = null`).
- **Раскладка (`layout`):**
  - `width`: `1..12` (по умолчанию `6`);
  - `height`: `40..720` px (по умолчанию `320`; для графиков `line_chart`, `bar_chart`, `area_chart`, `scatter_plot` и таблиц `table` минимум `120` px);
  - `x`: `0..11 | null` (должно выполняться `x + width <= 12`);
  - `y`: `>= 0 | null`.
- **Контейнер и поверхность:** `surface` (`"none" | "soft" | "card"`, по умолчанию `"card"`, для `text`, `page_link`, `layout_group`, `tab_group` — `"none"`), `showBorder` (`bool | null`), `showBackground` (`bool | null`).
- **Выравнивание, отступы и размеры:** `contentAlignment` (`"left" | "center" | "right"`), `verticalAlignment` (`"top" | "center" | "bottom"`), `padding` (`0..32`, по умолчанию `12`), `spacing` (`0..16`, по умолчанию `0`), `contentWidth` (`"content" | "stretch"`, по умолчанию `"stretch"`), `heightMode` (`"auto" | "fixed" | null`).
- **Типографика элементов:** `elementFontSize` (`"auto" | 12 | 14 | 16 | 18 | 20 | 24 | 28 | 32`), `elementTextColor` (`#RRGGBB`, по умолчанию `"#d4d4d8"`), `elementFontWeight` (`"normal" | "bold"`), `elementFontStyle` (`"normal" | "italic"`).

## Поддерживаемые компоненты (13 типов)

| `type` | Группа | Streamlit рендеринг | Ключевые поля модели |
| --- | --- | --- | --- |
| `selectbox` | `filters` | `st.selectbox`, `st.radio`, `st.segmented_control`, `st.pills`, `st.multiselect` | `field`, `scope="global"`, `widget` (`selectbox`, `radio`, `segmented`, `pills`, `multiselect`) |
| `data_control` | `filters` | `st.slider`, `st.date_input`, `st.toggle` | `field`, `scope="global"`, `controlType` (`range`, `date`, `toggle`) |
| `line_chart` | `views` | `st.vega_lite_chart` (line + hover) | `x`, `y`, `aggregation`, `sort`, `sortBy`, `color`, `colorMode="solid"`, `palette`, `axisLabel*`, `axisTitle*` |
| `bar_chart` | `views` | `st.vega_lite_chart` (bar) | `x`, `y`, `aggregation`, `sort`, `sortBy`, `color`, `colorMode` (`solid`, `gradient`, `categorical`), `palette`, `axisLabel*`, `axisTitle*` |
| `area_chart` | `views` | `st.vega_lite_chart` (area + hover) | `x`, `y`, `aggregation`, `sort`, `sortBy`, `color`, `colorMode="solid"`, `palette`, `axisLabel*`, `axisTitle*` |
| `scatter_plot` | `views` | `st.vega_lite_chart` (point + hover) | `x`, `y`, `aggregation`, `sort`, `sortBy`, `color`, `colorMode` (`solid`, `gradient`, `categorical`), `palette`, `axisLabel*`, `axisTitle*` |
| `metric` | `views` | `st.metric` | `field`, `description`, `aggregation` (`sum`, `mean`, `count`, `min`, `max`) |
| `progress` | `views` | `st.progress` | `field`, `aggregation` (`sum`..`max`), `minimum`, `maximum` (`maximum > minimum`), `showValue`, `color` (`#RRGGBB`) |
| `table` | `views` | `st.dataframe` | `columns`, `tableMode` (`data` \| `pivot`), `rowMode` (`all` \| `limit`), `rowLimit` (`1..10000`, default `50`), `hideIndex`, `pivotIndex`, `pivotValue`, `pivotAggregation` |
| `text` | `views` | `st.markdown` | `content` (`min_length=1`), `fontSize` (`12..32`), `fontWeight`, `fontStyle`, `color` (`#RRGGBB`), `textAlign` (`left` \| `center` \| `right`) |
| `page_link` | `views` | `st.button` + `st.switch_page` / `st.page_link` | `targetPageId`, `displayStyle` (`button` \| `link`), `buttonColor` (`#RRGGBB`) |
| `layout_group` | `views` | `st.container` | `direction` (`vertical` \| `horizontal`), `gap` (`0..32`), `padding` (`0..32`), `horizontalAlignment`, `verticalAlignment`, `wrap` |
| `tab_group` | `views` | `st.tabs` + `st.columns` | `tabs` (`1..8` элементов `{id, label}`), `activeTabId`, `gap` (`0..32`), `padding` (`0..32`) |

### Детали валидации компонентов

- **Графики (`ChartView`):**
  - `aggregation`: `none`, `sum`, `mean`, `count`, `min`, `max`;
  - `sort`: `none`, `asc`, `desc`; `sortBy`: `x` или `y`;
  - `color`: цвет серии `#RRGGBB`; `colorMode`: `solid`, `gradient`, `categorical` (режимы `gradient` и `categorical` разрешены только для `bar_chart` и `scatter_plot`);
  - `palette`: от 2 до 8 цветов `#RRGGBB`;
  - настройки осей: `axisLabelFontSize` (`8..24`, по умолчанию `11`), `axisLabelColor` (`#RRGGBB`), `axisTitleFontSize` (`8..24`, по умолчанию `12`), `axisTitleColor` (`#RRGGBB`).
- **Метрики и прогресс:** поддерживают агрегации `sum`, `mean`, `count`, `min`, `max` (значение `none` не допускается). Для `progress` обязательно `maximum > minimum`.
- **Таблицы (`table`):** поддерживают обычный режим (`data`, до `10000` строк при `rowMode="limit"`) и сводный режим (`pivot`, обязательны поля `pivotIndex` и `pivotValue`).

## Данные для холста редактора (Recharts в браузере)

Во время сборки дашборда React-редактор сразу строит графики, таблицы и метрики в браузере с помощью библиотеки **Recharts** (быстрый визуальный черновик) и запрашивает с бэкенда ограниченную выборку строк:

```http
GET /datasets/{dataset_id}/preview?limit=10000
```

Параметр `limit` по умолчанию равен `10000` (допустимый диапазон — `1..10000`). Ответ содержит `datasetId`, `fields`, `fieldTypes`, `rows`, `returnedRows` и `limit`. Автоопределение типов колонок в `fieldTypes` поддерживает значения `number`, `datetime`, `boolean` и `string`. Эта выборка используется только для отрисовки черновика в браузере (Recharts) и не сохраняется внутри схемы проекта.

## Жизненный цикл предпросмотра на Streamlit (`/preview`)

Чтобы увидеть итоговое приложение на реальном движке **Streamlit** (по сгенерированному коду и на всём загруженном датасете, без скачивания архива), фронтенд управляет сессией предпросмотра на фоновом Streamlit-сервере (порт `8501`):

- `POST /preview` — создать сессию предпросмотра на Streamlit (валидирует `schema`, проверяет доступ ко всем `dataSources[*].datasetId`);
- `PUT /preview/{session_id}` — обновить схему в сессии и увеличить `revision`;
- `GET /preview/{session_id}` — внутренний запрос из `preview_render.py` (получает `schema`, `datasetsPaths`, `revision` и `updatedAt` для рендеринга в Streamlit);
- `DELETE /preview/{session_id}` — удалить сессию.

Неактивные сессии автоматически удаляются по TTL.

## Экспортируемый Streamlit-проект

Скачанный `app.py` использует нативные компоненты Streamlit и Vega-Lite. Раскладка воспроизводится через адаптивную 12-колоночную CSS Grid-сетку с теми же размерами строк и отступов, что и холст конструктора:

- `layout.x` и `layout.y` сохраняют положение компонента на холсте (для схем без `x/y` backend автоматически подбирает свободное место без пересечений);
- `layout.width` задаёт ширину в колонках (`1..12`), `layout.height` — целевую высоту карточки;
- фильтры, элементы управления, метрики, таблицы, контейнеры, вкладки и графики размещаются в единой сетке;
- при наличии нескольких страниц в `pages` или `page_link` автоматически формируется многостраничная навигация через `st.navigation` и `st.Page`;
- интерактивные фильтры (`selectbox`) и элементы управления (`data_control`) хранят состояние в `st.session_state`, после чего компоненты пересчитываются на отфильтрованных датасетах по их `datasetId`;
- на узких экранах карточки переходят в вертикальный адаптивный список.

## Environment

| Variable | Default | Description |
| --- | --- | --- |
| `SECRET_KEY` | built-in dev fallback | Секретный ключ для подписи JWT-токенов (рекомендуется задавать свой в production) |
| `PREVIEW_PORT` | `8501` | Порт фонового Streamlit-сервера предпросмотра |
| `PREVIEW_HOST` | `127.0.0.1` (`0.0.0.0` в Docker) | Хост Streamlit-сервера предпросмотра |
| `PREVIEW_PUBLIC_URL` | `http://localhost:8501` | Публичный URL для формирования `previewUrl` |
| `PREVIEW_SESSION_TTL_SECONDS` | `1800` | Время жизни неактивной сессии предпросмотра (в секундах) |
| `STREAMLIT_BUILDER_API_BASE` | `http://localhost:8000` | Адрес FastAPI для запросов из `preview_render.py` |

## Tests

```bash
python -B -m unittest discover -s tests -v
```

