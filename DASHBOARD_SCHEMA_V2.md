**English** | [Русский](DASHBOARD_SCHEMA_V2.ru.md)

# Dashboard Schema v2 — Backend Contract

The backend accepts a declarative schema from the React editor, validates it with Pydantic v2 (`app/schemas/dashboard.py`), and uses it as the single source of truth both for the built-in **Streamlit** preview (`/preview`) and for the exported `app.py`.

## Root Schema Structure (`DashboardSchema`)

| Field | Type / constraints | Default | Description |
| --- | --- | --- | --- |
| `version` | `1 \| 2` | `2` | Schema contract version |
| `dashboard` | `{ title: str, grid: { columns: 12 } }` | `title: "Untitled dashboard"` | Dashboard metadata and 12-column grid config |
| `pages` | `list[DashboardPage]` (`min_length=1`) | `[{"id": "page-main", "title": "Главная", "order": 1}]` | Dashboard pages (`id`, `title`, `order >= 1`; `id` must be unique) |
| `dataSources` | `list[DataSource]` (`min_length=1`) | — | Data sources: `type="backend_dataset"`, `datasetId`, `name`, `format`, `delimiter`, `encoding`, `sheetName`, `fields` |
| `filters` | `list[SelectboxFilter \| DataControlFilter]` | `[]` | Global filters and data controls |
| `views` | `list[DashboardView]` | `[]` | Visual components, text blocks, page links, and containers |

### Schema Integrity Rules

- Component `id` values must be unique within `filters`, within `views`, and across the entire dashboard.
- Every component's `pageId` must reference an existing page in `pages`.
- `targetPageId` on `page_link` must reference an existing page in `pages`.
- `layout_group` and `tab_group` containers cannot be nested inside each other (`parentId` is forbidden on them).
- If a component specifies `parentId`, the parent must be a `layout_group` or `tab_group` on the same page (`pageId`).

## Common Component Fields (`ComponentBase`)

All component models are configured with `extra="forbid"` and `populate_by_name=True` (both `camelCase` aliases and `snake_case` field names are accepted; serialized output uses `camelCase`).

- **Identification & binding:** `id` (`str`), `order` (`int >= 1`), `title` (`str = ""`), `pageId` (`str = "page-main"`), `datasetId` (`str | null = null`), `parentId` (`str | null = null`), `tabId` (`str | null = null`).
- **Layout (`layout`):**
  - `width`: `1..12` (default `6`);
  - `height`: `40..720` px (default `320`; charts `line_chart`, `bar_chart`, `area_chart`, `scatter_plot` and tables `table` require at least `120` px);
  - `x`: `0..11 | null` (`x + width <= 12` must hold);
  - `y`: `>= 0 | null`.
- **Container & surface:** `surface` (`"none" | "soft" | "card"`, default `"card"`, or `"none"` for `text`, `page_link`, `layout_group`, `tab_group`), `showBorder` (`bool | null`), `showBackground` (`bool | null`).
- **Alignment, spacing & sizing:** `contentAlignment` (`"left" | "center" | "right"`), `verticalAlignment` (`"top" | "center" | "bottom"`), `padding` (`0..32`, default `12`), `spacing` (`0..16`, default `0`), `contentWidth` (`"content" | "stretch"`, default `"stretch"`), `heightMode` (`"auto" | "fixed" | null`).
- **Element typography:** `elementFontSize` (`"auto" | 12 | 14 | 16 | 18 | 20 | 24 | 28 | 32`), `elementTextColor` (`#RRGGBB`, default `"#d4d4d8"`), `elementFontWeight` (`"normal" | "bold"`), `elementFontStyle` (`"normal" | "italic"`).

## Supported Components (13 Types)

| `type` | Group | Streamlit rendering | Key model fields |
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
| `tab_group` | `views` | `st.tabs` + `st.columns` | `tabs` (`1..8` items `{id, label}`), `activeTabId`, `gap` (`0..32`), `padding` (`0..32`) |

### Component Validation Details

- **Charts (`ChartView`):**
  - `aggregation`: `none`, `sum`, `mean`, `count`, `min`, `max`;
  - `sort`: `none`, `asc`, `desc`; `sortBy`: `x` or `y`;
  - `color`: series color `#RRGGBB`; `colorMode`: `solid`, `gradient`, `categorical` (`gradient` and `categorical` are only allowed for `bar_chart` and `scatter_plot`);
  - `palette`: 2 to 8 `#RRGGBB` colors;
  - axis settings: `axisLabelFontSize` (`8..24`, default `11`), `axisLabelColor` (`#RRGGBB`), `axisTitleFontSize` (`8..24`, default `12`), `axisTitleColor` (`#RRGGBB`).
- **Metrics and progress:** support `sum`, `mean`, `count`, `min`, `max` aggregations (`none` is not allowed). `progress` requires `maximum > minimum`.
- **Tables (`table`):** support standard mode (`data`, up to `10000` rows when `rowMode="limit"`) and pivot mode (`pivot`, requiring `pivotIndex` and `pivotValue`).

## Editor Canvas Data (Recharts in Browser)

While assembling a dashboard, the React editor renders charts, tables, and metrics directly in the browser using **Recharts** (for fast visual feedback) and fetches a bounded row sample from the backend:

```http
GET /datasets/{dataset_id}/preview?limit=10000
```

`limit` defaults to `10000` (allowed range: `1..10000`). The response contains `datasetId`, `fields`, `fieldTypes`, `rows`, `returnedRows`, and `limit`. Automatic column type inference in `fieldTypes` supports `number`, `datetime`, `boolean`, and `string`. This sample is used solely for rendering the draft on the browser canvas (Recharts) and is never persisted inside the project schema.

## Streamlit Preview Lifecycle (`/preview`)

To view the final application running on the real **Streamlit** engine (compiled from the generated code against the full uploaded dataset, without downloading a ZIP archive), the frontend manages a preview session on the background Streamlit server (port `8501`):

- `POST /preview` — create a Streamlit preview session (validates `schema`, verifies access to every `dataSources[*].datasetId`);
- `PUT /preview/{session_id}` — update the session schema and increment `revision`;
- `GET /preview/{session_id}` — internal endpoint called by `preview_render.py` (returns `schema`, `datasetsPaths`, `revision`, and `updatedAt` for Streamlit rendering);
- `DELETE /preview/{session_id}` — delete the session.

Inactive sessions are automatically cleaned up on TTL expiration.

## Exported Streamlit Project

The downloaded `app.py` uses native Streamlit and Vega-Lite components. Layout is reproduced via a responsive 12-column CSS Grid matching the builder canvas row heights and spacing:

- `layout.x` and `layout.y` preserve component placement on the canvas (for schemas without `x/y`, the backend automatically picks free non-overlapping slots);
- `layout.width` sets column span (`1..12`), `layout.height` sets the target card height;
- filters, data controls, metrics, tables, containers, tabs, and charts are placed within a unified grid;
- when `pages` contains multiple pages or `page_link` is used, multi-page navigation is automatically generated via `st.navigation` and `st.Page`;
- interactive filters (`selectbox`) and data controls (`data_control`) store state in `st.session_state`, and components recalculate from filtered datasets matched by their `datasetId`;
- on narrow screens, cards collapse into a responsive vertical stack.

## Environment

| Variable | Default | Description |
| --- | --- | --- |
| `SECRET_KEY` | built-in dev fallback | Secret key used to sign JWT tokens (set your own in production) |
| `PREVIEW_PORT` | `8501` | Port of the background Streamlit preview server |
| `PREVIEW_HOST` | `127.0.0.1` (`0.0.0.0` in Docker) | Host of the Streamlit preview server |
| `PREVIEW_PUBLIC_URL` | `http://localhost:8501` | Public URL used to build `previewUrl` |
| `PREVIEW_SESSION_TTL_SECONDS` | `1800` | Inactive preview session lifetime (in seconds) |
| `STREAMLIT_BUILDER_API_BASE` | `http://localhost:8000` | FastAPI base URL used by `preview_render.py` |

## Tests

```bash
python -B -m unittest discover -s tests -v
```
