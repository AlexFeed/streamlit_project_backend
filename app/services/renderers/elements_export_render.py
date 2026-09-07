PAGE_STYLE = """
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
    background: linear-gradient(145deg, rgba(19, 22, 29, .96), rgba(12, 14, 19, .96));
    box-shadow: 0 14px 36px rgba(0, 0, 0, .18);
  }
  [data-testid="stMetric"] {
    height: 100%;
    padding: .35rem .25rem;
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
    font-size: .82rem;
    font-weight: 650;
  }
  [data-baseweb="select"] > div {
    min-height: 44px;
    border-color: rgba(148, 163, 184, .22);
    border-radius: 11px;
    background: #0b0e14;
  }
  footer {
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


ELEMENTS_RENDERER_SOURCE = r'''
GRID_COLUMNS = 12
GRID_ROW_HEIGHT = 20
GRID_GAP = 16
ALL_VALUES_LABEL = "Все значения"

CARD_STYLE = {
    "width": "100%",
    "height": "100%",
    "boxSizing": "border-box",
    "overflow": "hidden",
    "border": "1px solid rgba(148, 163, 184, 0.15)",
    "borderRadius": 3.5,
    "background": (
        "radial-gradient(circle at 100% 0, rgba(59,130,246,.08), transparent 34%),"
        "linear-gradient(145deg, #13161d 0%, #0d0f14 100%)"
    ),
    "boxShadow": "0 16px 42px rgba(0, 0, 0, 0.24)",
}
CONTENT_STYLE = {
    "width": "100%",
    "height": "100%",
    "minWidth": 0,
    "minHeight": 0,
    "boxSizing": "border-box",
    "display": "flex",
    "flexDirection": "column",
    "padding": 2,
}
CHART_STYLE = {
    "width": "100%",
    "height": "100%",
    "minWidth": 0,
    "minHeight": 0,
    "flex": 1,
    "position": "relative",
    "overflow": "hidden",
}
NIVO_THEME = {
    "background": "transparent",
    "text": {"fill": "#cbd5e1", "fontSize": 11},
    "axis": {
        "domain": {"line": {"stroke": "#334155"}},
        "ticks": {
            "line": {"stroke": "#334155"},
            "text": {"fill": "#94a3b8", "fontSize": 10},
        },
        "legend": {"text": {"fill": "#94a3b8", "fontSize": 11}},
    },
    "grid": {"line": {"stroke": "#1f2937", "strokeWidth": 1}},
    "tooltip": {
        "container": {
            "background": "#0b0e14",
            "color": "#f8fafc",
            "fontSize": 12,
            "border": "1px solid rgba(148,163,184,.18)",
            "borderRadius": 10,
            "boxShadow": "0 16px 40px rgba(0,0,0,.35)",
        },
    },
}


SUPPORTED_AGGREGATIONS = {"none", "sum", "mean", "count", "min", "max"}
SUPPORTED_SORT_ORDERS = {"none", "asc", "desc"}
SUPPORTED_SORT_FIELDS = {"x", "y"}


def prepare_chart_data(dataframe, x, y, aggregation='none', sort_order='none', sort_by='x'):
    if not x or not y:
        raise ValueError('Для графика должны быть выбраны поля X и Y')
    missing_fields = [field for field in (x, y) if field not in dataframe.columns]
    if missing_fields:
        raise KeyError(', '.join(missing_fields))
    if aggregation not in SUPPORTED_AGGREGATIONS:
        raise ValueError(f'Неизвестная агрегация: {aggregation}')
    if sort_order not in SUPPORTED_SORT_ORDERS:
        raise ValueError(f'Неизвестная сортировка: {sort_order}')
    if sort_by not in SUPPORTED_SORT_FIELDS:
        raise ValueError(f'Неизвестное поле сортировки: {sort_by}')
    chart_df = dataframe[[x, y]].dropna().copy()
    if chart_df.empty:
        return chart_df
    if aggregation != 'count':
        chart_df[y] = pd.to_numeric(chart_df[y], errors='coerce')
        chart_df = chart_df.dropna(subset=[y])
    if aggregation != 'none':
        chart_df = (
            chart_df
            .groupby(x, as_index=False, dropna=False, sort=False)[y]
            .agg(aggregation)
        )
    if sort_order != 'none':
        chart_df = chart_df.sort_values(
            by=y if sort_by == 'y' else x,
            ascending=sort_order == 'asc',
            kind='stable',
        )
    return chart_df


def calculate_metric(dataframe, field, aggregation='sum'):
    if not field or field not in dataframe.columns:
        raise KeyError(field)
    if aggregation == 'count':
        return int(dataframe[field].count())
    if aggregation not in SUPPORTED_AGGREGATIONS - {'none'}:
        raise ValueError(f'Неизвестная агрегация: {aggregation}')
    values = pd.to_numeric(dataframe[field], errors='coerce').dropna()
    if values.empty:
        return 0
    result = values.agg(aggregation)
    return result.item() if hasattr(result, 'item') else result


def format_metric(value):
    if isinstance(value, float):
        return f"{value:,.2f}".replace(",", " ")
    return f"{value:,}".replace(",", " ")


def component_state_key(component):
    # Keep widget keys stable and safe for Streamlit session state.
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
    values = sorted(
        dataframe[field]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )
    return [ALL_VALUES_LABEL, *values[:500]]


def selected_filter_value(component, dataframe):
    options = filter_options(component, dataframe)
    selected = str(
        st.session_state.get(
            component_state_key(component),
            ALL_VALUES_LABEL,
        )
    )
    return selected if selected in options else ALL_VALUES_LABEL


def apply_filters(schema, dataframe):
    filtered = dataframe.copy()
    for component in sorted(
        schema.get("filters", []),
        key=lambda item: item.get("order", 0),
    ):
        field = component.get("field")
        if field not in dataframe.columns:
            continue
        selected = selected_filter_value(component, dataframe)
        if selected != ALL_VALUES_LABEL:
            filtered = filtered[filtered[field].astype(str) == selected]
    return filtered


def render_filter_controls(schema, dataframe):
    filters = sorted(
        schema.get("filters", []),
        key=lambda item: item.get("order", 0),
    )
    if not filters:
        return

    with st.container(border=True):
        st.markdown("#### Фильтры")
        for row_start in range(0, len(filters), 4):
            row_filters = filters[row_start:row_start + 4]
            columns = st.columns(4, gap="medium")
            for column, component in zip(columns, row_filters):
                field = component.get("field")
                with column:
                    if field not in dataframe.columns:
                        st.warning(f"Колонка «{field}» не найдена.")
                        continue
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
        mui.Alert(str(error), severity="warning")
        return
    mui.Typography(
        format_metric(value),
        sx={
            "fontSize": "clamp(28px, 4vw, 46px)",
            "fontWeight": 760,
            "lineHeight": 1.05,
            "letterSpacing": "-0.04em",
            "color": "#f8fafc",
            "marginTop": 1,
            "maxWidth": "100%",
            "whiteSpace": "nowrap",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
        },
    )
    description = component.get("description")
    if description:
        mui.Typography(
            description,
            sx={"fontSize": 12, "color": "#94a3b8", "marginTop": 1},
        )


def grid_height(component):
    requested = int(component.get("layout", {}).get("height", 320))
    pitch = GRID_ROW_HEIGHT + GRID_GAP
    return max(4, (requested + GRID_GAP + pitch - 1) // pitch)


def components_from_schema(schema):
    return sorted(
        schema.get("views", []),
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
        x = max(0, min(GRID_COLUMNS - width, int(layout.get("x", 0))))
        placed.append({
            "x": x,
            "y": max(0, int(layout.get("y", 0))),
            "w": width,
            "h": grid_height(component),
            "component": component,
        })

    for component in automatic:
        width = max(
            1,
            min(GRID_COLUMNS, int(component.get("layout", {}).get("width", 6))),
        )
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


def hex_to_rgb(color):
    value = color.lstrip("#")
    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
    )


def interpolate_color(value, minimum, maximum, palette):
    if minimum == maximum:
        return palette[0]
    ratio = max(0.0, min(1.0, (value - minimum) / (maximum - minimum)))
    position = ratio * (len(palette) - 1)
    left_index = int(position)
    right_index = min(len(palette) - 1, left_index + 1)
    progress = position - left_index
    left = hex_to_rgb(palette[left_index])
    right = hex_to_rgb(palette[right_index])
    channels = [
        round(left[channel] + (right[channel] - left[channel]) * progress)
        for channel in range(3)
    ]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def quantized_gradient_color(value, minimum, maximum, palette, steps=9):
    if minimum == maximum:
        return palette[0]
    steps = max(2, int(steps))
    ratio = max(0.0, min(1.0, (value - minimum) / (maximum - minimum)))
    bucket_ratio = round(ratio * (steps - 1)) / (steps - 1)
    bucket_value = minimum + bucket_ratio * (maximum - minimum)
    return interpolate_color(bucket_value, minimum, maximum, palette)


def build_chart_records(view, dataframe):
    chart_df = prepare_chart_data(
        dataframe,
        view.get("x"),
        view.get("y"),
        view.get("aggregation", "none"),
        view.get("sort", "none"),
        view.get("sortBy", "x"),
    )
    if chart_df.empty:
        return []

    x = view.get("x")
    y = view.get("y")
    palette = view.get("palette") or ["#0ea5e9", "#8b5cf6"]
    mode = view.get("colorMode", "solid")
    values = chart_df[y].astype(float)
    minimum = float(values.min())
    maximum = float(values.max())
    category_colors = {}
    category_occurrences = {}
    records = []

    for index, (_, row) in enumerate(chart_df.iterrows()):
        category = str(row[x])
        value = float(row[y])
        if view.get("type") == "scatter_plot":
            try:
                x_value = float(row[x])
            except (TypeError, ValueError):
                continue
        else:
            occurrence = category_occurrences.get(category, 0) + 1
            category_occurrences[category] = occurrence
            x_value = category if occurrence == 1 else f"{category} · {occurrence}"
        if mode == "gradient":
            # A scatter plot is split into a small number of colored series.
            # Quantization prevents hundreds of one-point series while keeping
            # the visual value gradient.
            if view.get("type") == "scatter_plot":
                color = quantized_gradient_color(
                    value,
                    minimum,
                    maximum,
                    palette,
                )
            else:
                color = interpolate_color(value, minimum, maximum, palette)
        elif mode == "categorical":
            color = category_colors.setdefault(
                category,
                palette[len(category_colors) % len(palette)],
            )
        else:
            color = view.get("color", "#3b82f6")
        records.append({
            "category": x_value if view.get("type") != "scatter_plot" else category,
            "categoryLabel": category,
            "xValue": x_value,
            "value": value,
            "color": color,
            "index": index,
        })
    return records


def downsample_records(records, limit):
    if len(records) <= limit:
        return records
    if limit <= 1:
        return records[:1]
    last = len(records) - 1
    indexes = [round(index * last / (limit - 1)) for index in range(limit)]
    return [records[index] for index in indexes]


def axis_tick_values(records, layout_width):
    """Return a readable, evenly distributed set of categorical X ticks."""
    values = []
    seen = set()
    for record in records:
        value = record["xValue"]
        marker = str(value)
        if marker not in seen:
            seen.add(marker)
            values.append(value)
    tick_budget = max(3, min(12, int(layout_width or 6)))
    if len(values) <= tick_budget:
        return values
    last = len(values) - 1
    indexes = [
        round(index * last / (tick_budget - 1))
        for index in range(tick_budget)
    ]
    return [values[index] for index in indexes]


def render_chart(view, dataframe):
    try:
        records = build_chart_records(view, dataframe)
    except (KeyError, ValueError, TypeError):
        mui.Alert("Проверьте выбранные поля и агрегацию.", severity="warning")
        return
    if not records:
        mui.Alert("Нет данных для отображения.", severity="info")
        return

    chart_type = view.get("type")
    color = view.get("color", "#3b82f6")
    component_layout = view.get("layout", {})
    compact = int(component_layout.get("height", 320)) < 240
    x_ticks = (
        []
        if chart_type == "scatter_plot"
        else axis_tick_values(records, component_layout.get("width", 6))
    )
    rotate_labels = bool(x_ticks) and (
        len(x_ticks) > 6
        or max(len(str(value)) for value in x_ticks) > 8
    )
    common_axis = {
        "tickRotation": -35 if rotate_labels else 0,
        "legendOffset": 48 if compact else (56 if rotate_labels else 40),
        "legendPosition": "middle",
        "tickSize": 0,
        "tickPadding": 8,
    }

    with mui.Box(sx=CHART_STYLE):
        if chart_type == "bar_chart":
            visible = downsample_records(records, 80)
            nivo.Bar(
                data=visible,
                keys=["value"],
                indexBy="category",
                margin={
                    "top": 8 if compact else 18,
                    "right": 10 if compact else 18,
                    "bottom": 48 if compact else (76 if rotate_labels else 58),
                    "left": 46 if compact else 64,
                },
                padding=0.32,
                colors={"datum": "data.color"},
                borderRadius=5,
                enableLabel=len(visible) <= 12,
                labelSkipHeight=22,
                labelTextColor="#e2e8f0",
                axisBottom={
                    **common_axis,
                    "legend": None if compact else view.get("x"),
                    "tickValues": x_ticks,
                },
                axisLeft={
                    **common_axis,
                    "legend": None if compact else view.get("y"),
                    "legendOffset": -38 if compact else -52,
                    "tickRotation": 0,
                },
                theme=NIVO_THEME,
                animate=True,
                motionConfig="gentle",
                isInteractive=True,
            )
            return

        limit = 1600 if chart_type == "scatter_plot" else 600
        visible = downsample_records(records, limit)
        series = [{
            "id": view.get("title", "Данные"),
            "data": [
                {
                    "x": record["xValue"],
                    "y": record["value"],
                }
                for record in visible
            ],
        }]
        common = {
            "data": series,
            "margin": {
                "top": 8 if compact else 18,
                "right": 10 if compact else 22,
                "bottom": 42 if compact else 58,
                "left": 46 if compact else 64,
            },
            "colors": [color],
            "theme": NIVO_THEME,
            "axisBottom": {
                **common_axis,
                "legend": None if compact else view.get("x"),
                "tickValues": x_ticks,
            },
            "axisLeft": {
                **common_axis,
                "legend": None if compact else view.get("y"),
                "legendOffset": -38 if compact else -52,
                "tickRotation": 0,
            },
            "animate": True,
            "motionConfig": "gentle",
        }
        if chart_type == "scatter_plot":
            if view.get("colorMode", "solid") in {"gradient", "categorical"}:
                grouped = {}
                for record in visible:
                    grouped.setdefault(record["color"], []).append({
                        "x": record["xValue"],
                        "y": record["value"],
                    })
                common["data"] = [
                    {
                        "id": f"series-{index}",
                        "color": point_color,
                        "data": points,
                    }
                    for index, (point_color, points) in enumerate(grouped.items())
                ]
                # Nivo colors scatter nodes by series.  Supplying the series
                # colors as an ordinal list works consistently in
                # streamlit-elements; datum-based accessors otherwise fall
                # back to black in the generated app.
                common["colors"] = [
                    series_item["color"]
                    for series_item in common["data"]
                ]
            nivo.ScatterPlot(
                **common,
                nodeSize=7,
                blendMode="normal",
                useMesh=True,
                isInteractive=True,
            )
        else:
            nivo.Line(
                **common,
                enableArea=chart_type == "area_chart",
                areaOpacity=0.2,
                curve="linear",
                pointSize=0 if len(visible) > 80 else 6,
                pointBorderWidth=0,
                useMesh=True,
                enableSlices="x",
                isInteractive=True,
            )


def render_component(component, filtered_dataframe):
    component_type = component.get("type")
    title = component.get("title") or {
        "metric": "Метрика",
    }.get(component_type, "График")
    mui.Typography(
        title,
        sx={
            "fontSize": 15,
            "fontWeight": 700,
            "color": "#f8fafc",
            "letterSpacing": "-0.01em",
            "lineHeight": 1.25,
            "marginBottom": .5,
            "whiteSpace": "nowrap",
            "overflow": "hidden",
            "textOverflow": "ellipsis",
        },
    )
    if component_type == "metric":
        render_metric(component, filtered_dataframe)
    else:
        render_chart(component, filtered_dataframe)


def render_dashboard(schema, dataframe):
    render_filter_controls(schema, dataframe)
    filtered = apply_filters(schema, dataframe)
    components = components_from_schema(schema)
    placements = pack_components(components)
    if not placements:
        return

    layout = [
        dashboard.Item(
            item["component"]["id"],
            item["x"],
            item["y"],
            item["w"],
            item["h"],
            minW=1,
            minH=4,
            static=True,
        )
        for item in placements
    ]

    with elements("builder_dashboard"):
        with dashboard.Grid(
            layout,
            cols={
                "xxs": GRID_COLUMNS,
                "xs": GRID_COLUMNS,
                "sm": GRID_COLUMNS,
                "md": GRID_COLUMNS,
                "lg": GRID_COLUMNS,
            },
            rowHeight=GRID_ROW_HEIGHT,
            margin=[GRID_GAP, GRID_GAP],
            containerPadding=[0, 0],
            isDraggable=False,
            isResizable=False,
            compactType=None,
            preventCollision=True,
            autoSize=True,
        ):
            for item in placements:
                component = item["component"]
                with mui.Paper(key=component["id"], elevation=0, sx=CARD_STYLE):
                    with mui.Box(sx=CONTENT_STYLE):
                        render_component(component, filtered)
'''


def render_elements_dashboard_code(schema: dict) -> list[str]:
    return [
        f"st.markdown({PAGE_STYLE!r}, unsafe_allow_html=True)",
        f"DASHBOARD_SCHEMA = {schema!r}",
        "",
        *ELEMENTS_RENDERER_SOURCE.strip().splitlines(),
        "",
        "render_dashboard(DASHBOARD_SCHEMA, df)",
        "",
    ]
