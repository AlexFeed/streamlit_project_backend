import html
import math

import pandas as pd
import streamlit as st

NATIVE_PAGE_STYLE = """
<style>
  .stApp {
    background:
      radial-gradient(circle at 80% -10%, rgba(37, 99, 235, .14), transparent 32rem),
      radial-gradient(circle at 8% 6%, rgba(14, 165, 233, .08), transparent 25rem),
      #09090b;
    color: #f8fafc;
  }
  [data-testid="stHeader"],
  header[data-testid="stHeader"] {
    display: none !important;
  }
  .block-container {
    width: 100%;
    /* 1040px minus page padding gives the same 960px working width as the
       editor canvas. Grid columns, wrapping and component heights therefore
       stay truthful between the builder and the generated application. */
    max-width: 1040px;
    padding: 2rem 2.5rem 3rem;
  }
  .block-container h1 {
    margin: 0;
    color: #f8fafc;
    font-size: clamp(1.7rem, 2.7vw, 2.45rem);
    font-weight: 760;
    letter-spacing: -.045em;
    line-height: 1.25;
  }
  [data-testid="stCaptionContainer"] {
    margin: .4rem 0 1.5rem;
    color: #94a3b8;
    font-size: 0.92rem;
  }
  [data-testid="stVerticalBlockBorderWrapper"] {
    border-color: rgba(148, 163, 184, .15);
    border-radius: 16px;
    background:
      radial-gradient(circle at 100% 0, rgba(59,130,246,.08), transparent 34%),
      linear-gradient(145deg, rgba(19, 22, 29, .98), rgba(12, 14, 19, .98));
    box-shadow: 0 14px 36px rgba(0, 0, 0, .18);
  }
  [data-testid="stMetric"] {
    padding: .25rem .15rem;
  }
  [data-testid="stMetricLabel"] {
    color: #94a3b8;
  }
  [data-testid="stMetricValue"] {
    color: #f8fafc;
    font-size: clamp(1.35rem, 2vw, 2rem);
    font-weight: 760;
    letter-spacing: -.04em;
    overflow: visible !important;
    text-overflow: clip !important;
    white-space: nowrap !important;
  }
  [data-testid="stMetricValue"] > div {
    overflow: visible !important;
    text-overflow: clip !important;
    white-space: nowrap !important;
  }
  [data-testid="stSelectbox"] label {
    color: #cbd5e1;
    font-size: .86rem;
    font-weight: 650;
  }
  [data-baseweb="select"] > div {
    min-height: 44px;
    border-color: rgba(148, 163, 184, .22);
    border-radius: 11px;
    background: #0b0e14;
  }
  footer {
    display: none !important;
    visibility: hidden;
  }
  @media (max-width: 760px) {
    .block-container {
      padding-right: 1rem;
      padding-left: 1rem;
    }
  }
</style>
"""

GRID_COLUMNS = 12
DEFAULT_PAGE_ID = "page-main"
GRID_ROW_HEIGHT = 20
# Keep the generated Streamlit layout visually identical to the editor canvas.
# Horizontal and vertical neighbours use the same minimum 8 px gap.
GRID_COLUMN_GAP = 8
GRID_ROW_GAP = 8
CARD_CHROME_HEIGHT = 96
# Space used by the component title, Streamlit block gap and card padding.
# It must not be handed to the chart itself or the fixed card starts scrolling.
STREAMLIT_CHROME_HEIGHT = 76
ALL_VALUES_LABEL = "Все значения"
SUPPORTED_AGGREGATIONS = {"none", "sum", "mean", "count", "min", "max"}
SUPPORTED_SORT_ORDERS = {"none", "asc", "desc"}
SUPPORTED_SORT_FIELDS = {"x", "y"}


def prepare_chart_data(dataframe, x, y, aggregation="none", sort_order="none", sort_by="x"):
    if not x or not y:
        raise ValueError("Для графика должны быть выбраны поля X и Y")
    missing_fields = [field for field in (x, y) if field not in dataframe.columns]
    if missing_fields:
        raise KeyError(", ".join(missing_fields))
    if aggregation not in SUPPORTED_AGGREGATIONS:
        raise ValueError(f"Неизвестная агрегация: {aggregation}")
    if sort_order not in SUPPORTED_SORT_ORDERS:
        raise ValueError(f"Неизвестная сортировка: {sort_order}")
    if sort_by not in SUPPORTED_SORT_FIELDS:
        raise ValueError(f"Неизвестное поле сортировки: {sort_by}")

    chart_df = dataframe[[x, y]].dropna().copy()
    if chart_df.empty:
        return chart_df
    if aggregation != "count":
        chart_df[y] = pd.to_numeric(chart_df[y], errors="coerce")
        chart_df = chart_df.dropna(subset=[y])
    if aggregation != "none":
        chart_df = (
            chart_df
            .groupby(x, as_index=False, dropna=False, sort=False)[y]
            .agg(aggregation)
        )
    if sort_order != "none":
        chart_df = chart_df.sort_values(
            by=y if sort_by == "y" else x,
            ascending=sort_order == "asc",
            kind="stable",
        )
    return chart_df


def calculate_metric(dataframe, field, aggregation="sum"):
    if not field or field not in dataframe.columns:
        raise KeyError(field)
    if aggregation == "count":
        return int(dataframe[field].count())
    if aggregation not in SUPPORTED_AGGREGATIONS - {"none"}:
        raise ValueError(f"Неизвестная агрегация: {aggregation}")
    values = pd.to_numeric(dataframe[field], errors="coerce").dropna()
    if values.empty:
        return 0
    result = values.agg(aggregation)
    return result.item() if hasattr(result, "item") else result


def format_metric(value):
    if isinstance(value, float):
        return f"{value:,.2f}".replace(",", " ")
    return f"{value:,}".replace(",", " ")


def component_state_key(component):
    component_id = str(component.get("id", "unknown"))
    safe_id = "".join(
        character if character.isalnum() or character == "_" else "_"
        for character in component_id
    )
    return f"builder_filter_{safe_id}"


def filter_options(component, dataframe):
    field = component.get("field")
    if field not in dataframe.columns:
        return [ALL_VALUES_LABEL]
    values = sorted(dataframe[field].dropna().astype(str).unique().tolist())
    return [ALL_VALUES_LABEL, *values[:500]]


def selected_filter_value(component, dataframe):
    options = filter_options(component, dataframe)
    state_value = st.session_state.get(component_state_key(component))
    if component.get("widget", "selectbox") == "multiselect":
        selected = state_value if isinstance(state_value, list) else []
        allowed = set(options[1:])
        return [value for value in selected if value in allowed]
    selected = str(state_value or ALL_VALUES_LABEL)
    return selected if selected in options else ALL_VALUES_LABEL


def resolve_dataset_id(component, datasets):
    dataset_id = component.get("datasetId")
    if dataset_id and dataset_id in datasets:
        return dataset_id
    return next(iter(datasets), None)


def apply_filters(schema, datasets, page_id=None):
    filtered_datasets = dict(datasets)
    filters = schema.get("filters", [])
    if page_id is not None:
        filters = [
            component
            for component in filters
            if component.get("pageId", DEFAULT_PAGE_ID) == page_id
        ]
    for component in sorted(filters, key=lambda item: item.get("order", 0)):
        dataset_id = resolve_dataset_id(component, datasets)
        if not dataset_id or dataset_id not in filtered_datasets:
            continue
        source_df = datasets[dataset_id]
        filtered_df = filtered_datasets[dataset_id]
        field = component.get("field")
        if field not in source_df.columns:
            continue
        selected = selected_filter_value(component, source_df)
        if isinstance(selected, list) and selected:
            filtered_datasets[dataset_id] = filtered_df[
                filtered_df[field].astype(str).isin(selected)
            ]
        elif selected != ALL_VALUES_LABEL and not isinstance(selected, list):
            filtered_datasets[dataset_id] = filtered_df[filtered_df[field].astype(str) == selected]
    return filtered_datasets


def automatic_component_height(component):
    component_type = component.get("type")
    padding = max(0, int(component.get("padding", 0))) * 2

    if component_type == "text":
        font_size = max(8, int(component.get("fontSize", 16)))
        width = max(
            2,
            min(GRID_COLUMNS, int(component.get("layout", {}).get("width", 6))),
        )
        available_width = max(64, width * 96 - padding)
        content = str(component.get("content") or "")
        lines = content.splitlines() or [""]
        content_lines = sum(
            max(
                1,
                math.ceil(len(line) * font_size * 0.58 / available_width),
            )
            for line in lines
        )
        title_lines = 1 if component.get("title") else 0
        line_height = max(24, font_size * 1.5)
        return math.ceil(
            content_lines * line_height
            + title_lines * 20
            + padding
        )
    if component_type == "page_link":
        return 40 + padding
    if component_type == "metric":
        # st.metric has its own label/value spacing in addition to our card
        # padding. Reserve the complete widget height so the following grid
        # item cannot start inside the metric card.
        return 58 + (18 if component.get("description") else 0) + padding
    if component_type == "selectbox":
        return 56 + padding
    return int(component.get("layout", {}).get("height", 320))


def automatic_container_height(component):
    surface = component.get(
        "surface",
        "none" if component.get("type") in {"text", "page_link"} else "card",
    )
    show_border = component.get("showBorder")
    if show_border is None:
        show_border = surface == "card"
    return automatic_component_height(component) + (2 if show_border else 0)


def grid_height(component):
    requested = int(component.get("layout", {}).get("height", 320))
    component_type = component.get("type")
    if component_type in {"text", "metric", "selectbox", "page_link"}:
        height = automatic_component_height(component)
        automatic_rows = max(
            1,
            math.ceil(
                (height + GRID_ROW_GAP)
                / (GRID_ROW_HEIGHT + GRID_ROW_GAP)
            ),
        )
        if component_type == "text" or component.get("heightMode") == "auto":
            return automatic_rows
        pitch = GRID_ROW_HEIGHT + GRID_ROW_GAP
        requested_rows = max(1, (requested + GRID_ROW_GAP + pitch - 1) // pitch)
        # Text may not be clipped below its wrapped lines. Other compact
        # widgets intentionally support a smaller manual card height.
        return requested_rows
    chrome_height = (
        0
        if component_type in {"text", "metric", "selectbox", "page_link"}
        else CARD_CHROME_HEIGHT
    )
    pitch = GRID_ROW_HEIGHT + GRID_ROW_GAP
    total_height = requested + chrome_height
    return max(1, (total_height + GRID_ROW_GAP + pitch - 1) // pitch)


def components_from_schema(schema, page_id=None, parent_id=None):
    components = [*schema.get("filters", []), *schema.get("views", [])]
    if page_id is not None:
        components = [
            component
            for component in components
            if component.get("pageId", DEFAULT_PAGE_ID) == page_id
        ]
    components = [
        component
        for component in components
        if component.get("parentId") == parent_id
    ]
    return sorted(
        components,
        key=lambda item: item.get("order", 0),
    )


def all_components_from_schema(schema, page_id=None):
    components = [*schema.get("filters", []), *schema.get("views", [])]
    if page_id is not None:
        components = [
            component
            for component in components
            if component.get("pageId", DEFAULT_PAGE_ID) == page_id
        ]
    return sorted(components, key=lambda item: item.get("order", 0))


def pages_from_schema(schema):
    pages = schema.get("pages") or [
        {"id": DEFAULT_PAGE_ID, "title": "Главная", "order": 1}
    ]
    return sorted(pages, key=lambda page: page.get("order", 0))


def pack_components(components):
    placed = []

    def overlaps(candidate, current):
        return (
                candidate["x"] < current["x"] + current["w"]
                and candidate["x"] + candidate["w"] > current["x"]
                and candidate["y"] < current["y"] + current["h"]
                and candidate["y"] + candidate["h"] > current["y"]
        )

    ordered = sorted(components, key=lambda item: item.get("order", 0))
    explicit = []
    automatic = []
    for component in ordered:
        layout = component.get("layout", {})
        if isinstance(layout.get("x"), int) and isinstance(layout.get("y"), int):
            explicit.append(component)
        else:
            automatic.append(component)

    for component in explicit:
        layout = component.get("layout", {})
        width = max(1, min(GRID_COLUMNS, int(layout.get("width", 6))))
        source_x = max(0, min(GRID_COLUMNS - width, int(layout.get("x", 0))))
        source_y = max(0, int(layout.get("y", 0)))
        candidate = {
            "x": source_x,
            "y": source_y,
            "w": width,
            "h": grid_height(component),
            "component": component,
        }
        while True:
            collisions = [current for current in placed if overlaps(candidate, current)]
            if not collisions:
                break
            candidate["y"] = max(current["y"] + current["h"] for current in collisions)
        placed.append(candidate)

    for component in automatic:
        width = max(1, min(GRID_COLUMNS, int(component.get("layout", {}).get("width", 6))))
        height = grid_height(component)
        position = None
        for y in range(10000):
            for x in range(GRID_COLUMNS - width + 1):
                candidate = {"x": x, "y": y, "w": width, "h": height}
                if not any(overlaps(candidate, current) for current in placed):
                    position = candidate
                    break
            if position:
                break
        placed.append({
            **(position or {"x": 0, "y": 0, "w": width, "h": height}),
            "component": component,
        })

    return sorted(placed, key=lambda item: item["component"].get("order", 0))


def grid_pixel_height(grid_rows):
    return (
            max(1, int(grid_rows)) * GRID_ROW_HEIGHT
            + max(0, int(grid_rows) - 1) * GRID_ROW_GAP
    )


def card_container_key(component):
    return f"card_{component_state_key(component)}"


def dashboard_grid_style(placements, components=None):
    max_row = max(
        (item["y"] + item["h"] for item in placements),
        default=1,
    )
    rules = [
        "<style>",
        ".st-key-dashboard_grid {",
        "  display: grid !important;",
        f"  grid-template-columns: repeat({GRID_COLUMNS}, minmax(0, 1fr));",
        f"  grid-template-rows: repeat({max_row}, {GRID_ROW_HEIGHT}px);",
        f"  column-gap: {GRID_COLUMN_GAP}px !important;",
        f"  row-gap: {GRID_ROW_GAP}px !important;",
        f"  gap: {GRID_ROW_GAP}px {GRID_COLUMN_GAP}px !important;",
        "  align-items: stretch;",
        "}",
        # Streamlit wraps every keyed container in a layout wrapper. Its
        # default block spacing used to be added on top of our grid gap,
        # making vertical neighbours farther apart than horizontal ones.
        ".st-key-dashboard_grid > [data-testid=\"stLayoutWrapper\"] {",
        "  margin: 0 !important;",
        "  padding-block: 0 !important;",
        "}",
    ]
    for item in placements:
        component = item["component"]
        key_class = f"st-key-{card_container_key(component)}"
        compact_component = component.get("type") in {
            "text", "metric", "selectbox", "page_link",
        }
        automatic_height = (
            compact_component
            and component.get("heightMode", "auto") == "auto"
        )
        minimum_height = (
            automatic_container_height(component)
            if automatic_height
            else None
        )
        item_rules = [
            (
                ".st-key-dashboard_grid > [data-testid=\"stLayoutWrapper\"]"
                f":has(.{key_class}) {{"
            ),
            f"  grid-column: {item['x'] + 1} / span {item['w']};",
            f"  grid-row: {item['y'] + 1} / span {item['h']};",
            "  min-width: 0;",
            "  box-sizing: border-box;",
            f"  padding: {int(component.get('spacing', 0))}px;",
            "  height: auto;" if automatic_height else "  height: 100%;",
        ]
        if automatic_height:
            item_rules.extend([
                f"  min-height: {minimum_height}px;",
                "  align-self: start;",
                "  overflow: visible;",
            ])
        item_rules.append("}")
        rules.extend(item_rules)

    styled_components = components or [
        item["component"] for item in placements
    ]
    styled_components = sorted(
        styled_components,
        key=lambda component: (
            component.get("parentId") is not None,
            component.get("order", 0),
        ),
    )
    for component in styled_components:
        key_class = f"st-key-{card_container_key(component)}"
        surface = component.get(
            "surface",
            "none" if component.get("type") in {"text", "page_link"} else "card",
        )
        show_background = component.get("showBackground")
        if show_background is None:
            show_background = surface in {"soft", "card"}
        if show_background:
            rules.extend([
                f".{key_class} {{",
                "  background: rgba(24, 24, 27, 0.58);",
                "  border-radius: 0.75rem;",
                "}",
            ])
        compact_component = component.get("type") in {
            "text", "metric", "selectbox", "page_link",
        }
        automatic_height = (
            compact_component
            and component.get("heightMode", "auto") == "auto"
        )
        if automatic_height:
            minimum_height = automatic_container_height(component)
            rules.extend([
                f".{key_class} {{",
                "  height: auto !important;",
                f"  min-height: {minimum_height}px !important;",
                "  overflow: visible !important;",
                "  justify-content: flex-start !important;",
                "}",
                f".{key_class} > [data-testid=\"stVerticalBlock\"] {{",
                "  gap: 0 !important;",
                "}",
                (
                    f".{key_class}[data-testid=\"stVerticalBlockBorderWrapper\"], "
                    f".{key_class} [data-testid=\"stVerticalBlockBorderWrapper\"] {{"
                ),
                "  height: auto !important;",
                "  min-height: 0 !important;",
                "  overflow: visible !important;",
                "}",
                (
                    f".{key_class} [data-testid=\"stElementContainer\"], "
                    f".{key_class} [data-testid=\"stMarkdown\"], "
                    f".{key_class} [data-testid=\"stMarkdown\"] > div {{"
                ),
                "  height: auto !important;",
                "  min-height: 0 !important;",
                "  overflow: visible !important;",
                "}",
            ])
        component_padding = int(component.get("padding", 12))
        show_border = component.get("showBorder")
        if show_border is None:
            show_border = surface == "card"
        safe_inline_padding = (
            max(component_padding, 4)
            if component.get("type") == "text" and show_border
            else component_padding
        )
        rules.extend([
            f".{key_class} {{",
            f"  padding: {component_padding}px;",
            f"  padding-inline: {safe_inline_padding}px;",
            "  overflow-y: hidden !important;",
            "}",
            f".{key_class} > [data-testid=\"stVerticalBlock\"] {{",
            "  overflow-y: hidden !important;",
            "}",
        ])
        text_color = component.get("elementTextColor", "#d4d4d8")
        font_size = component.get("elementFontSize", "auto")
        font_weight = component.get("elementFontWeight", "normal")
        font_style = component.get("elementFontStyle", "normal")
        typography_selectors = (
            f".{key_class} p, .{key_class} label, .{key_class} button, .{key_class} a, "
            f".{key_class} [data-testid=\"stMetricValue\"], "
            f".{key_class} [data-testid=\"stMetricLabel\"]"
        )
        rules.extend([
            f"{typography_selectors} {{",
            f"  color: {text_color} !important;",
            f"  font-weight: {font_weight} !important;",
            f"  font-style: {font_style} !important;",
        ])
        if font_size != "auto":
            rules.append(f"  font-size: {int(font_size)}px !important;")
        rules.append("}")
        if component.get("type") == "metric":
            rules.extend([
                f".{key_class} [data-testid=\"stMetricValue\"],",
                f".{key_class} [data-testid=\"stMetricValue\"] > div {{",
                "  overflow: visible !important;",
                "  text-overflow: clip !important;",
                "  white-space: nowrap !important;",
                "}",
            ])
        if component.get("type") == "page_link" and component.get("displayStyle", "button") == "button":
            button_color = component.get("buttonColor", "#f47721")
            rules.extend([
                f".{key_class} [data-testid=\"stButton\"] button {{",
                f"  background: {button_color} !important;",
                f"  border-color: {button_color} !important;",
                "  color: #ffffff !important;",
                "}",
            ])
    rules.extend([
        "@media (max-width: 760px) {",
        "  .st-key-dashboard_grid {",
        "    display: flex !important;",
        "    flex-direction: column;",
        f"    gap: {GRID_ROW_GAP}px !important;",
        "  }",
        "  .st-key-dashboard_grid > [data-testid=\"stLayoutWrapper\"] {",
        "    width: 100%;",
        "    height: auto;",
        "    transform: none !important;",
        "  }",
        "}",
        "</style>",
    ])
    return "\n".join(rules)


def downsample_frame(dataframe, limit):
    if len(dataframe) <= limit:
        return dataframe
    if limit <= 1:
        return dataframe.iloc[:1]
    last = len(dataframe) - 1
    indexes = sorted({round(index * last / (limit - 1)) for index in range(limit)})
    return dataframe.iloc[indexes]


def chart_point_limit(view):
    layout = view.get("layout", {})
    width = max(1, int(layout.get("width", 6)))
    height = max(120, int(layout.get("height", 320)))
    chart_type = view.get("type")
    if chart_type == "bar_chart":
        return max(24, min(100, width * 10))
    if chart_type == "scatter_plot":
        return max(180, min(700, width * height // 5))
    return max(120, min(600, width * height // 4))


def infer_x_type(series, field, chart_type):
    if chart_type == "bar_chart":
        return "nominal"
    if pd.api.types.is_numeric_dtype(series):
        return "quantitative"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "temporal"
    field_name = str(field or "").lower()
    date_hints = ("date", "time", "day", "month", "year", "дата", "время", "день", "месяц", "год")
    return "temporal" if any(hint in field_name for hint in date_hints) else "nominal"


def axis_tick_values(values, layout_width):
    unique_values = list(dict.fromkeys(values))
    tick_budget = max(3, min(12, int(layout_width or 6)))
    if len(unique_values) <= tick_budget:
        return unique_values
    last = len(unique_values) - 1
    indexes = [round(index * last / (tick_budget - 1)) for index in range(tick_budget)]
    return [unique_values[index] for index in indexes]


def prepare_plot_frame(view, dataframe):
    x = view.get("x")
    y = view.get("y")
    chart_df = prepare_chart_data(
        dataframe,
        x,
        y,
        view.get("aggregation", "none"),
        view.get("sort", "none"),
        view.get("sortBy", "x"),
    )
    if chart_df.empty:
        return chart_df, "nominal"

    chart_df = downsample_frame(chart_df, chart_point_limit(view)).copy()
    x_type = infer_x_type(chart_df[x], x, view.get("type"))
    if x_type == "temporal":
        chart_df[x] = pd.to_datetime(chart_df[x], errors="coerce")
        chart_df = chart_df.dropna(subset=[x])

    plot_df = pd.DataFrame({"x": chart_df[x], "y": chart_df[y].astype(float)})
    plot_df["label"] = plot_df["x"].astype(str)
    if x_type == "nominal" and view.get("type") != "scatter_plot":
        counts = {}
        labels = []
        for value in plot_df["label"]:
            occurrence = counts.get(value, 0) + 1
            counts[value] = occurrence
            labels.append(value if occurrence == 1 else f"{value} · {occurrence}")
        plot_df["x"] = labels
    return plot_df, x_type


def color_encoding(view, chart_type):
    mode = view.get("colorMode", "solid")
    palette = view.get("palette") or ["#0ea5e9", "#8b5cf6"]
    if mode == "gradient" and chart_type in {"bar_chart", "scatter_plot"}:
        return {
            "field": "y",
            "type": "quantitative",
            "scale": {"range": palette},
            "legend": None,
        }
    if mode == "categorical" and chart_type in {"bar_chart", "scatter_plot"}:
        return {
            "field": "label",
            "type": "nominal",
            "scale": {"range": palette},
            "legend": None,
        }
    return {"value": view.get("color", palette[0])}


def render_filter(component, dataframe):
    field = component.get("field")
    if field not in dataframe.columns:
        st.warning(f"Колонка «{field}» не найдена.")
        return
    options = filter_options(component, dataframe)
    state_key = component_state_key(component)
    title = (component.get("title") or "").strip()
    label = title or field
    label_visibility = "visible" if title else "collapsed"
    widget = component.get("widget", "selectbox")
    widget_width = component.get("contentWidth", "stretch")

    if widget == "multiselect":
        selected = st.session_state.get(state_key)
        if not isinstance(selected, list):
            st.session_state[state_key] = []
        st.multiselect(
            label,
            options[1:],
            key=state_key,
            label_visibility=label_visibility,
            width=320 if widget_width == "content" else widget_width,
        )
    else:
        if st.session_state.get(state_key) not in options:
            st.session_state[state_key] = ALL_VALUES_LABEL
        if widget == "radio":
            st.radio(
                label,
                options,
                key=state_key,
                label_visibility=label_visibility,
                horizontal=True,
                width=widget_width,
            )
        elif widget == "segmented":
            st.segmented_control(
                label,
                options,
                key=state_key,
                label_visibility=label_visibility,
                required=True,
                width=widget_width,
            )
        elif widget == "pills":
            st.pills(
                label,
                options,
                key=state_key,
                label_visibility=label_visibility,
                required=True,
                width=widget_width,
            )
        else:
            st.selectbox(
                label,
                options,
                key=state_key,
                label_visibility=label_visibility,
                width=280 if widget_width == "content" else widget_width,
            )


def render_metric(component, dataframe):
    try:
        value = calculate_metric(
            dataframe,
            component.get("field"),
            component.get("aggregation", "sum"),
        )
    except (KeyError, ValueError) as error:
        st.warning(str(error))
        return
    description = (component.get("description") or "").strip()
    st.metric(
        label=component.get("title") or "Метрика",
        value=format_metric(value),
        help=description or None,
        border=False,
        width=component.get("contentWidth", "stretch"),
        height="content",
    )


def render_text(component):
    title = component.get("title")
    content = component.get("content") or ""
    if title:
        st.markdown(f"**{title}**")
    uses_default_style = (
        int(component.get("fontSize", 16)) == 16
        and component.get("fontWeight", "normal") == "normal"
        and component.get("fontStyle", "normal") == "normal"
        and component.get("color", "#d4d4d8").lower() == "#d4d4d8"
        and component.get("textAlign", "left") == "left"
    )
    if uses_default_style:
        st.markdown(content)
        return

    safe_content = html.escape(content).replace("\n", "<br>")
    style = "; ".join([
        f"font-size: {component.get('fontSize', 16)}px",
        f"font-weight: {component.get('fontWeight', 'normal')}",
        f"font-style: {component.get('fontStyle', 'normal')}",
        f"color: {component.get('color', '#d4d4d8')}",
        f"text-align: {component.get('textAlign', 'left')}",
        "line-height: 1.5",
        "white-space: pre-wrap",
        "overflow-wrap: anywhere",
    ])
    st.markdown(
        f'<div style="{style}">{safe_content}</div>',
        unsafe_allow_html=True,
    )


def render_page_link(component, navigation_pages):
    target_page = navigation_pages.get(component.get("targetPageId"))
    if target_page is None:
        st.warning("Страница для перехода не найдена.")
        return

    label = component.get("title") or "Открыть страницу"
    if component.get("displayStyle", "button") == "link":
        st.page_link(
            target_page,
            label=label,
            width=component.get("contentWidth", "content"),
        )
    elif st.button(
        label,
        key=f"navigate_{component_state_key(component)}",
        type="primary",
        width=component.get("contentWidth", "content"),
    ):
        st.switch_page(target_page)


def render_table(component, dataframe, available_height):
    if component.get("tableMode", "data") == "pivot":
        index_field = component.get("pivotIndex")
        value_field = component.get("pivotValue")
        aggregation = component.get("pivotAggregation", "sum")
        if index_field not in dataframe.columns or value_field not in dataframe.columns:
            st.warning("Выберите поля для сводной таблицы.")
            return
        if aggregation == "count":
            table_data = dataframe.groupby(index_field, dropna=False).size().reset_index(name=value_field)
        else:
            pivot_source = dataframe[[index_field, value_field]].copy()
            pivot_source[value_field] = pd.to_numeric(pivot_source[value_field], errors="coerce")
            table_data = (
                pivot_source.dropna(subset=[value_field])
                .groupby(index_field, dropna=False, as_index=False)[value_field]
                .agg(aggregation)
            )
    else:
        requested_columns = component.get("columns") or []
        columns = [
            column for column in requested_columns
            if column in dataframe.columns
        ] or list(dataframe.columns)
        table_data = dataframe.loc[:, columns]
    if component.get("rowMode", "limit") == "limit":
        table_data = table_data.head(int(component.get("rowLimit", 50)))
    st.dataframe(
        table_data,
        width="stretch",
        height="content",
        hide_index=component.get("hideIndex", True),
    )


def render_chart(view, dataframe, available_height):
    try:
        plot_df, x_type = prepare_plot_frame(view, dataframe)
    except (KeyError, ValueError, TypeError):
        st.warning("Проверьте выбранные поля и агрегацию.")
        return
    if plot_df.empty:
        st.info("Нет данных для отображения.")
        return

    chart_type = view.get("type")
    layout_width = view.get("layout", {}).get("width", 6)
    nominal_ticks = (
        axis_tick_values(plot_df["x"].tolist(), layout_width)
        if x_type == "nominal"
        else None
    )
    x_axis = {
        "labelColor": view.get("axisLabelColor", "#94a3b8"),
        "labelFontSize": int(view.get("axisLabelFontSize", 11)),
        "titleColor": view.get("axisTitleColor", "#94a3b8"),
        "titleFontSize": int(view.get("axisTitleFontSize", 12)),
        "grid": False,
        "labelOverlap": "greedy",
        "labelLimit": 110,
        "labelAngle": -35 if x_type == "nominal" and len(plot_df) > 6 else 0,
    }
    if nominal_ticks is not None:
        x_axis["values"] = nominal_ticks
    elif x_type == "temporal":
        x_axis.update({"format": "%d.%m.%Y", "tickCount": max(3, min(10, int(layout_width)))})

    tooltip = [
        {"field": "label", "type": "nominal", "title": view.get("x")},
        {"field": "y", "type": "quantitative", "title": view.get("y"), "format": ",.2f"},
    ]
    encoding = {
        "x": {
            "field": "x",
            "type": x_type,
            "title": view.get("x"),
            "sort": None,
            "axis": x_axis,
        },
        "y": {
            "field": "y",
            "type": "quantitative",
            "title": view.get("y"),
            "axis": {
                "labelColor": view.get("axisLabelColor", "#94a3b8"),
                "labelFontSize": int(view.get("axisLabelFontSize", 11)),
                "titleColor": view.get("axisTitleColor", "#94a3b8"),
                "titleFontSize": int(view.get("axisTitleFontSize", 12)),
                "gridColor": "#1f2937",
                "gridOpacity": .75,
            },
        },
        "color": color_encoding(view, chart_type),
    }

    if chart_type == "bar_chart":
        mark = {"type": "bar", "cornerRadiusTopLeft": 5, "cornerRadiusTopRight": 5}
    elif chart_type == "area_chart":
        mark = {"type": "area", "line": True, "opacity": .3}
    elif chart_type == "scatter_plot":
        mark = {"type": "point", "filled": True}
    else:
        mark = {"type": "line", "point": len(plot_df) <= 80, "strokeWidth": 2.5}

    spec = {
        "height": max(120, available_height),
        "autosize": {
            "type": "fit",
            "contains": "padding",
            "resize": True,
        },
        "padding": {
            "top": 4,
            "right": 4,
            "bottom": 4,
            "left": 4,
        },
        "config": {
            "background": "transparent",
            "view": {"stroke": None},
            "axis": {"domainColor": "#334155", "tickColor": "#334155"},
        },
    }
    if chart_type in {"line_chart", "area_chart"}:
        hover = {
            "name": "hover",
            "select": {
                "type": "point",
                "encodings": ["x"],
                "nearest": True,
                "on": "pointerover",
                "clear": "pointerout",
            },
        }
        spec["layer"] = [
            {"mark": mark, "encoding": encoding},
            {
                "params": [hover],
                "mark": {"type": "rule", "color": "#64748b", "strokeWidth": 1},
                "encoding": {
                    "x": encoding["x"],
                    "opacity": {
                        "condition": {"param": "hover", "empty": False, "value": .75},
                        "value": 0,
                    },
                    "tooltip": tooltip,
                },
            },
            {
                "transform": [{"filter": {"param": "hover", "empty": False}}],
                "mark": {
                    "type": "point",
                    "filled": True,
                    "size": 125,
                    "stroke": "#f8fafc",
                    "strokeWidth": 1.5,
                },
                "encoding": {
                    "x": encoding["x"],
                    "y": encoding["y"],
                    "color": encoding["color"],
                },
            },
        ]
    elif chart_type == "scatter_plot":
        hover = {
            "name": "hover",
            "select": {
                "type": "point",
                "nearest": True,
                "on": "pointerover",
                "clear": "pointerout",
            },
        }
        spec["layer"] = [
            {
                "mark": mark,
                "encoding": {
                    **encoding,
                    "size": {
                        "condition": {"param": "hover", "empty": False, "value": 150},
                        "value": 64,
                    },
                    "opacity": {
                        "condition": {"param": "hover", "empty": False, "value": 1},
                        "value": .72,
                    },
                },
            },
            {
                "params": [hover],
                "mark": {"type": "point", "filled": True, "size": 420, "opacity": .001},
                "encoding": {
                    "x": encoding["x"],
                    "y": encoding["y"],
                    "tooltip": tooltip,
                },
            },
        ]
    else:
        spec.update({
            "mark": mark,
            "encoding": {**encoding, "tooltip": tooltip},
        })
    st.vega_lite_chart(plot_df, spec, width="stretch", theme=None)


def render_component(
        component,
        source_dataframe,
        filtered_dataframe,
        container_height=None,
        navigation_pages=None,
        grouped=False,
):
    component_type = component.get("type")
    surface = component.get(
        "surface",
        "none" if component_type in {"text", "page_link"} else "card",
    )
    show_border = component.get("showBorder")
    if show_border is None:
        show_border = surface == "card"
    horizontal_alignment = component.get("contentAlignment", "left")
    vertical_alignment = component.get("verticalAlignment", "top")
    requested_height = int(component.get("layout", {}).get("height", 320))
    compact_component = component_type in {"text", "metric", "selectbox", "page_link"}
    height_mode = component.get("heightMode") or (
        "auto" if compact_component else "fixed"
    )
    is_content_sized = compact_component and (grouped or height_mode == "auto")
    if compact_component:
        content_height = max(60, requested_height)
    else:
        outer_height = container_height or requested_height + CARD_CHROME_HEIGHT
        content_height = max(140, outer_height - STREAMLIT_CHROME_HEIGHT)
    with st.container(
            height="content" if is_content_sized else (container_height or content_height),
            border=show_border,
            key=card_container_key(component),
            horizontal_alignment=horizontal_alignment,
            vertical_alignment=vertical_alignment,
    ):
        if component_type == "selectbox":
            render_filter(component, source_dataframe)
        elif component_type == "metric":
            render_metric(component, filtered_dataframe)
        elif component_type == "text":
            render_text(component)
        elif component_type == "page_link":
            render_page_link(component, navigation_pages or {})
        elif component_type == "table":
            st.markdown(f"**{component.get('title') or 'Таблица'}**")
            render_table(component, filtered_dataframe, content_height)
        else:
            st.markdown(f"**{component.get('title') or 'График'}**")
            render_chart(component, filtered_dataframe, content_height)


def render_layout_group(
        component,
        schema,
        datasets,
        filtered_datasets,
        container_height,
        navigation_pages,
):
    surface = component.get("surface", "none")
    show_border = component.get("showBorder")
    if show_border is None:
        show_border = surface == "card"
    gap = int(component.get("gap", 8))
    gap_value = None if gap == 0 else gap
    children = components_from_schema(
        schema,
        component.get("pageId", DEFAULT_PAGE_ID),
        component.get("id"),
    )
    compact_types = {"text", "metric", "selectbox", "page_link"}
    group_height = (
        "content"
        if children and all(child.get("type") in compact_types for child in children)
        else container_height
    )
    with st.container(
            height=group_height,
            border=show_border,
            key=card_container_key(component),
    ):
        title = component.get("title", "").strip()
        if title:
            st.markdown(f"**{title}**")
        with st.container(
                horizontal=component.get("direction", "vertical") == "horizontal",
                wrap=component.get("wrap", True),
                horizontal_alignment=component.get("horizontalAlignment", "left"),
                vertical_alignment=component.get("verticalAlignment", "top"),
                gap=gap_value,
        ):
            for child in children:
                if child.get("type") in {"text", "page_link"}:
                    render_component(
                        child,
                        None,
                        None,
                        None,
                        navigation_pages,
                        grouped=True,
                    )
                    continue
                dataset_id = resolve_dataset_id(child, datasets)
                render_component(
                    child,
                    datasets[dataset_id],
                    filtered_datasets[dataset_id],
                    None,
                    navigation_pages,
                    grouped=True,
                )


# Точка входа которая генерирует весь streamlit код
def render_dashboard(schema, datasets, page_id=None, navigation_pages=None):
    placements = pack_components(components_from_schema(schema, page_id))
    if not placements or not datasets:
        return
    st.markdown(NATIVE_PAGE_STYLE, unsafe_allow_html=True)
    st.markdown(
        dashboard_grid_style(
            placements,
            all_components_from_schema(schema, page_id),
        ),
        unsafe_allow_html=True,
    )
    filtered_datasets = apply_filters(schema, datasets, page_id)
    with st.container(key="dashboard_grid"):
        for item in sorted(placements, key=lambda value: (value["y"], value["x"])):
            component = item["component"]
            if component.get("type") == "layout_group":
                render_layout_group(
                    component,
                    schema,
                    datasets,
                    filtered_datasets,
                    grid_pixel_height(item["h"]),
                    navigation_pages,
                )
                continue
            if component.get("type") == "page_link":
                render_component(
                    component,
                    None,
                    None,
                    grid_pixel_height(item["h"]),
                    navigation_pages,
                )
                continue
            dataset_id = resolve_dataset_id(component, datasets)
            render_component(
                component,
                datasets[dataset_id],
                filtered_datasets[dataset_id],
                grid_pixel_height(item["h"]),
                navigation_pages,
            )


def render_multipage_dashboard(schema, datasets):
    pages = pages_from_schema(schema)
    has_page_links = any(
        view.get("type") == "page_link"
        for view in schema.get("views", [])
    )
    if len(pages) == 1 and not has_page_links:
        render_dashboard(schema, datasets, pages[0]["id"])
        return

    navigation_pages = {}
    for index, page in enumerate(pages):
        page_id = page["id"]

        def render_page(current_page_id=page_id):
            render_dashboard(
                schema,
                datasets,
                current_page_id,
                navigation_pages,
            )

        navigation_pages[page_id] = st.Page(
            render_page,
            title=page["title"],
            url_path=page_id,
            default=index == 0,
        )

    st.navigation(
        list(navigation_pages.values()),
        position="top" if len(pages) > 1 else "hidden",
    ).run()
