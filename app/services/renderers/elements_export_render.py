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
GRID_ROW_HEIGHT = 22
GRID_GAP = 16
CARD_CHROME_HEIGHT = 70

CARD_STYLE = {
    "height": "100%",
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
    "height": "100%",
    "boxSizing": "border-box",
    "display": "flex",
    "flexDirection": "column",
    "padding": 2,
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


def format_metric(value):
    if isinstance(value, float):
        return f"{value:,.2f}".replace(",", " ")
    return f"{value:,}".replace(",", " ")


def render_filters(schema, dataframe):
    filtered = dataframe.copy()
    filters = sorted(
        schema.get("filters", []),
        key=lambda item: item.get("order", 0),
    )
    if not filters:
        return filtered

    with st.container(border=True):
        columns = st.columns(min(4, len(filters)))
        for index, item in enumerate(filters):
            field = item.get("field")
            with columns[index % len(columns)]:
                if field not in dataframe.columns:
                    st.warning(f"Колонка «{field}» не найдена.")
                    continue
                selected = st.selectbox(
                    item.get("title", "Фильтр"),
                    ["Все значения"] + sorted(
                        dataframe[field]
                        .dropna()
                        .astype(str)
                        .unique()
                        .tolist()
                    ),
                    key=f"filter_{item.get('id')}",
                )
                if selected != "Все значения":
                    filtered = filtered[
                        filtered[field].astype(str) == selected
                    ]
    return filtered


def render_metrics(schema, dataframe):
    metrics = [
        item
        for item in sorted(
            schema.get("views", []),
            key=lambda value: value.get("order", 0),
        )
        if item.get("type") == "metric"
    ]
    if not metrics:
        return

    columns = st.columns(min(4, len(metrics)))
    for index, item in enumerate(metrics):
        with columns[index % len(columns)]:
            with st.container(border=True, height=150):
                try:
                    value = calculate_metric(
                        dataframe,
                        item.get("field"),
                        item.get("aggregation", "sum"),
                    )
                    st.metric(
                        item.get("title", "Метрика"),
                        format_metric(value),
                        help=item.get("description") or None,
                    )
                except (KeyError, ValueError) as error:
                    st.warning(str(error))


def grid_height(item):
    total = int(item.get("layout", {}).get("height", 320)) + CARD_CHROME_HEIGHT
    pitch = GRID_ROW_HEIGHT + GRID_GAP
    return max(7, (total + GRID_GAP + pitch - 1) // pitch)


def pack_views(views):
    placed = []

    def overlaps(candidate, current):
        return (
            candidate["x"] < current["x"] + current["w"]
            and candidate["x"] + candidate["w"] > current["x"]
            and candidate["y"] < current["y"] + current["h"]
            and candidate["y"] + candidate["h"] > current["y"]
        )

    for view in sorted(views, key=lambda item: item.get("order", 0)):
        width = int(view.get("layout", {}).get("width", 6))
        width = max(4, min(GRID_COLUMNS, width))
        height = grid_height(view)
        position = None
        for y in range(10000):
            for x in range(GRID_COLUMNS - width + 1):
                candidate = {"x": x, "y": y, "w": width, "h": height}
                if not any(overlaps(candidate, current) for current in placed):
                    position = candidate
                    break
            if position:
                break
        placed.append({**position, "view": view})
    return placed


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
            x_value = category
        if mode == "gradient":
            color = interpolate_color(value, minimum, maximum, palette)
        elif mode == "categorical":
            color = category_colors.setdefault(
                category,
                palette[len(category_colors) % len(palette)],
            )
        else:
            color = view.get("color", "#3b82f6")
        records.append({
            "category": category,
            "xValue": x_value,
            "value": value,
            "color": color,
            "index": index,
        })
    return records


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
    common_axis = {
        "tickRotation": -18,
        "legendOffset": 43,
        "legendPosition": "middle",
        "tickSize": 0,
        "tickPadding": 8,
    }

    with mui.Box(sx={"flex": 1, "minHeight": 0}):
        if chart_type == "bar_chart":
            nivo.Bar(
                data=records[:80],
                keys=["value"],
                indexBy="category",
                margin={"top": 18, "right": 18, "bottom": 58, "left": 64},
                padding=0.32,
                colors={"datum": "data.color"},
                borderRadius=5,
                enableLabel=len(records) <= 12,
                labelSkipHeight=22,
                labelTextColor="#e2e8f0",
                axisBottom={**common_axis, "legend": view.get("x")},
                axisLeft={
                    **common_axis,
                    "legend": view.get("y"),
                    "legendOffset": -52,
                    "tickRotation": 0,
                },
                theme=NIVO_THEME,
                animate=True,
                motionConfig="gentle",
                isInteractive=True,
            )
            return

        limit = 1600 if chart_type == "scatter_plot" else 600
        step = max(1, (len(records) + limit - 1) // limit)
        visible = records[::step]
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
            "margin": {"top": 18, "right": 22, "bottom": 58, "left": 64},
            "colors": [color],
            "theme": NIVO_THEME,
            "axisBottom": {**common_axis, "legend": view.get("x")},
            "axisLeft": {
                **common_axis,
                "legend": view.get("y"),
                "legendOffset": -52,
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
                common["colors"] = {"datum": "color"}
            nivo.ScatterPlot(
                **common,
                nodeSize=7,
                useMesh=True,
                isInteractive=True,
            )
        else:
            nivo.Line(
                **common,
                enableArea=chart_type == "area_chart",
                areaOpacity=0.2,
                curve="monotoneX",
                pointSize=0 if len(visible) > 80 else 6,
                pointBorderWidth=0,
                useMesh=True,
                enableSlices="x",
                isInteractive=True,
            )


def render_dashboard(schema, dataframe):
    filtered = render_filters(schema, dataframe)
    render_metrics(schema, filtered)
    charts = [
        item
        for item in schema.get("views", [])
        if item.get("type") != "metric"
    ]
    placements = pack_views(charts)
    if not placements:
        return

    layout = [
        dashboard.Item(
            item["view"]["id"],
            item["x"],
            item["y"],
            item["w"],
            item["h"],
            minW=4,
            minH=7,
        )
        for item in placements
    ]

    with elements("builder_dashboard"):
        with dashboard.Grid(
            layout,
            cols=GRID_COLUMNS,
            rowHeight=GRID_ROW_HEIGHT,
            margin=[GRID_GAP, GRID_GAP],
            isDraggable=False,
            isResizable=False,
        ):
            for item in placements:
                view = item["view"]
                with mui.Paper(key=view["id"], elevation=0, sx=CARD_STYLE):
                    with mui.Box(sx=CONTENT_STYLE):
                        mui.Typography(
                            view.get("title", "График"),
                            sx={
                                "fontSize": 15,
                                "fontWeight": 700,
                                "color": "#f8fafc",
                                "letterSpacing": "-0.01em",
                                "marginBottom": .5,
                            },
                        )
                        render_chart(view, filtered)
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
