import html

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
  [data-testid="stHeader"] {
    background: rgba(9, 9, 11, .75);
    backdrop-filter: blur(14px);
  }
  .block-container {
    width: 100%;
    max-width: 1540px;
    padding: 1.6rem 2rem 3rem;
  }
  .block-container h1 {
    margin: 0;
    color: #f8fafc;
    font-size: clamp(1.7rem, 2.7vw, 2.45rem);
    font-weight: 760;
    letter-spacing: -.045em;
  }
  [data-testid="stCaptionContainer"] {
    margin: .35rem 0 1rem;
    color: #94a3b8;
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
    font-size: clamp(1.8rem, 3vw, 2.65rem);
    font-weight: 760;
    letter-spacing: -.04em;
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
  footer { visibility: hidden; }
  @media (max-width: 760px) {
    .block-container {
      padding-right: 1rem;
      padding-left: 1rem;
    }
  }
</style>
"""

GRID_COLUMNS = 12
GRID_ROW_HEIGHT = 20
GRID_GAP = 16
CARD_CHROME_HEIGHT = 96
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
    selected = str(st.session_state.get(component_state_key(component), ALL_VALUES_LABEL))
    return selected if selected in options else ALL_VALUES_LABEL


def resolve_dataset_id(component, datasets):
    dataset_id = component.get("datasetId")
    if dataset_id and dataset_id in datasets:
        return dataset_id
    return next(iter(datasets), None)


def apply_filters(schema, datasets):
    filtered_datasets = dict(datasets)
    for component in sorted(schema.get("filters", []), key=lambda item: item.get("order", 0)):
        dataset_id = resolve_dataset_id(component, datasets)
        if not dataset_id or dataset_id not in filtered_datasets:
            continue
        source_df = datasets[dataset_id]
        filtered_df = filtered_datasets[dataset_id]
        field = component.get("field")
        if field not in source_df.columns:
            continue
        selected = selected_filter_value(component, source_df)
        if selected != ALL_VALUES_LABEL:
            filtered_datasets[dataset_id] = filtered_df[filtered_df[field].astype(str) == selected]
    return filtered_datasets


def grid_height(component):
    requested = int(component.get("layout", {}).get("height", 320))
    component_type = component.get("type")
    chrome_height = 0 if component_type in {"text", "metric"} else CARD_CHROME_HEIGHT
    pitch = GRID_ROW_HEIGHT + GRID_GAP
    total_height = requested + chrome_height
    return max(1, (total_height + GRID_GAP + pitch - 1) // pitch)


def components_from_schema(schema):
    return sorted(
        [*schema.get("filters", []), *schema.get("views", [])],
        key=lambda item: item.get("order", 0),
    )


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
        placed.append({
            "x": source_x,
            "y": source_y,
            "w": width,
            "h": grid_height(component),
            "component": component,
        })

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
            + max(0, int(grid_rows) - 1) * GRID_GAP
    )


def card_container_key(component):
    return f"card_{component_state_key(component)}"


def dashboard_grid_style(placements):
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
        f"  column-gap: {GRID_GAP}px !important;",
        f"  row-gap: {GRID_GAP}px !important;",
        "  align-items: stretch;",
        "}",
    ]
    for item in placements:
        key_class = f"st-key-{card_container_key(item['component'])}"
        item_rules = [
            (
                ".st-key-dashboard_grid > [data-testid=\"stLayoutWrapper\"]"
                f":has(.{key_class}) {{"
            ),
            f"  grid-column: {item['x'] + 1} / span {item['w']};",
            f"  grid-row: {item['y'] + 1} / span {item['h']};",
            "  min-width: 0;",
            "  height: 100%;",
        ]
        item_rules.append("}")
        rules.extend(item_rules)
    rules.extend([
        "@media (max-width: 760px) {",
        "  .st-key-dashboard_grid {",
        "    display: flex !important;",
        "    flex-direction: column;",
        f"    gap: {GRID_GAP}px !important;",
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
    if st.session_state.get(state_key) not in options:
        st.session_state[state_key] = ALL_VALUES_LABEL
    st.selectbox(
        component.get("title") or "Фильтр",
        options,
        key=state_key,
        help=f"Поле данных: {field}",
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
    title = html.escape(component.get("title") or "Метрика")
    formatted_value = html.escape(str(format_metric(value)))
    description = component.get("description") or (
        f"{component.get('aggregation', 'sum')} · {component.get('field', '')}"
    )
    safe_description = html.escape(description)
    card_height = max(60, int(component.get("layout", {}).get("height", 80)))
    content_height = max(28, card_height - 48)
    st.markdown(
        (
            '<div style="display:flex; flex-direction:column; height:100%;">'
            f'<div style="font-size:14px; font-weight:650; color:#f8fafc;">{title}</div>'
            f'<div style="min-height:{content_height}px; display:flex; flex:1; '
            'flex-direction:column; align-items:center; justify-content:center; '
            'text-align:center;">'
            f'<div style="font-size:36px; font-weight:700; line-height:1; color:#f8fafc;">'
            f'{formatted_value}</div>'
            f'<div style="margin-top:12px; font-size:14px; color:#a1a1aa;">'
            f'{safe_description}</div>'
            '</div></div>'
        ),
        unsafe_allow_html=True,
    )


def render_text(component):
    title = component.get("title")
    content = component.get("content") or ""
    if title:
        st.markdown(f"**{title}**")
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
        "labelColor": "#94a3b8",
        "titleColor": "#94a3b8",
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
                "labelColor": "#94a3b8",
                "titleColor": "#94a3b8",
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
):
    component_type = component.get("type")
    requested_height = int(component.get("layout", {}).get("height", 320))
    if component_type in {"text", "metric"}:
        content_height = max(60, requested_height)
    else:
        outer_height = container_height or requested_height + CARD_CHROME_HEIGHT
        content_height = max(140, outer_height - CARD_CHROME_HEIGHT)
    with st.container(
            height=container_height or content_height,
            border=True,
            key=card_container_key(component),
    ):
        if component_type == "selectbox":
            render_filter(component, source_dataframe)
        elif component_type == "metric":
            render_metric(component, filtered_dataframe)
        elif component_type == "text":
            render_text(component)
        else:
            st.markdown(f"**{component.get('title') or 'График'}**")
            render_chart(component, filtered_dataframe, content_height)


# Точка входа которая генерирует весь streamlit код
def render_dashboard(schema, datasets):
    placements = pack_components(components_from_schema(schema))
    if not placements or not datasets:
        return
    st.markdown(NATIVE_PAGE_STYLE, unsafe_allow_html=True)
    st.markdown(dashboard_grid_style(placements), unsafe_allow_html=True)
    filtered_datasets = apply_filters(schema, datasets)
    with st.container(key="dashboard_grid"):
        for item in sorted(placements, key=lambda value: (value["y"], value["x"])):
            component = item["component"]
            dataset_id = resolve_dataset_id(component, datasets)
            render_component(
                component,
                datasets[dataset_id],
                filtered_datasets[dataset_id],
                grid_pixel_height(item["h"]),
            )
