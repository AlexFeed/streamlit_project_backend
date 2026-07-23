from app.services.renderers.schema_utils import (
    balance_components_by_height,
    get_chart_views,
    get_component_height,
    get_component_width,
    get_components,
    get_filters,
    get_row_column_widths,
    get_views,
    get_summary_components,
    pack_equal_rows,
    pack_component_rows,
    python_string_literal,
    safe_variable_name,
)


CHART_METHODS = {
    "line_chart": "line_chart",
    "bar_chart": "bar_chart",
    "area_chart": "area_chart",
    "scatter_plot": "scatter_chart",
}


def indent_lines(lines: list[str], spaces: int) -> list[str]:
    prefix = " " * spaces
    return [f"{prefix}{line}" if line else "" for line in lines]


def render_code_dashboard(schema: dict) -> list[str]:
    lines: list[str] = []
    lines.extend(render_code_filter_state(schema))
    lines.extend(render_code_summary(schema))
    lines.extend(render_code_chart_layout(schema))
    return lines


def render_code_summary(schema: dict) -> list[str]:
    lines: list[str] = []

    for row_index, row in enumerate(
        pack_equal_rows(get_summary_components(schema))
    ):
        variable = f"summary_columns_{row_index}"
        lines.append(f"{variable} = st.columns({len(row)})")

        for column_index, component in enumerate(row):
            lines.append(f"with {variable}[{column_index}]:")

            if component.get("type") == "selectbox":
                height = get_component_height(component, 160)
                lines.append(
                    f"    with st.container(border=True, height={height}):"
                )
                lines.extend(
                    indent_lines(render_code_selectbox(component), 8)
                )
            else:
                lines.append("    with st.container(border=True):")
                lines.extend(
                    indent_lines(render_code_view(component), 8)
                )

        lines.append("")

    return lines


def render_code_chart_layout(schema: dict) -> list[str]:
    lines: list[str] = []
    pending: list[dict] = []
    section_index = 0

    def flush_pending() -> None:
        nonlocal section_index
        if not pending:
            return

        variable = f"chart_columns_{section_index}"
        lines.append(f"{variable} = st.columns(2)")

        for lane_index, lane in enumerate(
            balance_components_by_height(pending)
        ):
            if not lane:
                continue

            lines.append(f"with {variable}[{lane_index}]:")
            for view in lane:
                lines.append("    with st.container(border=True):")
                lines.extend(indent_lines(render_code_view(view), 8))

        lines.append("")
        pending.clear()
        section_index += 1

    for view in get_chart_views(schema):
        if get_component_width(view) >= 8:
            flush_pending()
            lines.append("with st.container(border=True):")
            lines.extend(indent_lines(render_code_view(view), 4))
            lines.append("")
        else:
            pending.append(view)

    flush_pending()
    return lines


def render_code_filter_state(schema: dict) -> list[str]:
    lines: list[str] = []

    for flt in get_filters(schema):
        field_value = flt.get("field")
        if not field_value:
            continue

        field = python_string_literal(field_value)
        component_id = safe_variable_name(
            flt.get("id", field_value),
            "filter",
        )
        state_variable = f"active_{component_id}"
        widget_key = python_string_literal(
            f"filter_{flt.get('id', field_value)}"
        )
        lines.extend([
            f"if {field} in filtered_df.columns:",
            f"    {state_variable} = st.session_state.get({widget_key}, 'Все')",
            f"    if {state_variable} != 'Все':",
            f"        filtered_df = filtered_df[filtered_df[{field}].astype(str) == {state_variable}]",
            "",
        ])

    return lines


def render_code_components(schema: dict) -> list[str]:
    components = get_components(schema)

    if not components:
        return [
            "st.info('Добавьте компоненты в редакторе.')",
            "",
        ]

    lines: list[str] = []

    for row_index, row in enumerate(pack_component_rows(components)):
        variable = f"dashboard_columns_{row_index}"
        lines.append(
            f"{variable} = st.columns({get_row_column_widths(row)!r})"
        )

        for column_index, component in enumerate(row):
            lines.append(f"with {variable}[{column_index}]:")

            if component.get("type") == "selectbox":
                height = get_component_height(component, 160)
                lines.append(
                    f"    with st.container(border=True, height={height}):"
                )
                lines.extend(
                    indent_lines(render_code_selectbox(component), 8)
                )
            else:
                lines.append("    with st.container(border=True):")
                lines.extend(
                    indent_lines(render_code_view(component), 8)
                )

        lines.append("")

    return lines


def render_code_filters(schema: dict) -> list[str]:
    filters = get_filters(schema)

    if not filters:
        return []

    lines = [
        "st.markdown('### Фильтры')",
        "",
    ]

    for row_index, row in enumerate(pack_component_rows(filters)):
        variable = f"filter_columns_{row_index}"
        lines.append(f"{variable} = st.columns({get_row_column_widths(row)!r})")

        for column_index, flt in enumerate(row):
            height = get_component_height(flt, 160)
            lines.extend([
                f"with {variable}[{column_index}]:",
                f"    with st.container(border=True, height={height}):",
            ])
            lines.extend(indent_lines(render_code_selectbox(flt), 8))

        lines.append("")

    return lines


def render_code_selectbox(flt: dict) -> list[str]:
    title = python_string_literal(flt.get("title"), "Фильтр")
    field_value = flt.get("field")
    field = python_string_literal(field_value)

    if not field_value:
        return ["st.warning('Для фильтра не выбрана колонка.')"]

    component_id = safe_variable_name(
        flt.get("id", field_value),
        "filter",
    )
    variable_name = f"selected_{component_id}"
    widget_key = python_string_literal(f"filter_{flt.get('id', field_value)}")
    warning = python_string_literal(
        f"Колонка «{field_value}» не найдена для фильтра."
    )

    return [
        f"if {field} in df.columns:",
        f"    {variable_name} = st.selectbox(",
        f"        {title},",
        f"        ['Все'] + sorted(df[{field}].dropna().astype(str).unique().tolist()),",
        f"        key={widget_key},",
        "    )",
        f"    if {variable_name} != 'Все':",
        f"        filtered_df = filtered_df[filtered_df[{field}].astype(str) == {variable_name}]",
        "else:",
        f"    st.warning({warning})",
    ]


def render_code_views(schema: dict) -> list[str]:
    views = get_views(schema)

    if not views:
        return [
            "st.info('Добавьте графики или метрики в редакторе.')",
            "",
        ]

    lines: list[str] = []

    for row_index, row in enumerate(pack_component_rows(views)):
        variable = f"view_columns_{row_index}"
        lines.append(f"{variable} = st.columns({get_row_column_widths(row)!r})")

        for column_index, view in enumerate(row):
            lines.extend([
                f"with {variable}[{column_index}]:",
                "    with st.container(border=True):",
            ])
            lines.extend(indent_lines(render_code_view(view), 8))

        lines.append("")

    return lines


def render_code_view(view: dict) -> list[str]:
    view_type = view.get("type")

    if view_type in CHART_METHODS:
        return render_code_chart(view, CHART_METHODS[view_type])
    if view_type == "metric":
        return render_code_metric(view)

    message = python_string_literal(
        f"Компонент «{view_type}» пока не поддерживается."
    )
    return [f"st.warning({message})"]


def render_code_chart(view: dict, chart_method: str) -> list[str]:
    title = python_string_literal(view.get("title"), "График")
    x_value = view.get("x")
    y_value = view.get("y")
    x = python_string_literal(x_value)
    y = python_string_literal(y_value)
    aggregation = python_string_literal(view.get("aggregation"), "none")
    sort_order = python_string_literal(view.get("sort"), "none")
    sort_by = python_string_literal(view.get("sortBy"), "x")
    color = python_string_literal(view.get("color"), "#3b82f6")
    height = get_component_height(view)
    missing_warning = python_string_literal(
        f"Колонки «{x_value}» и/или «{y_value}» не найдены."
    )
    color_mode = view.get("colorMode", "solid")
    uses_palette = (
        color_mode in {"gradient", "categorical"}
        and view.get("type") in {"bar_chart", "scatter_plot"}
    )

    lines = [
        f"st.markdown('#### ' + {title})",
        "try:",
        f"    chart_df = prepare_chart_data(filtered_df, {x}, {y}, {aggregation}, {sort_order}, {sort_by})",
        "except KeyError:",
        f"    st.warning({missing_warning})",
        "except ValueError as error:",
        "    st.warning(str(error))",
        "else:",
        "    if chart_df.empty:",
        "        st.info('Нет данных для отображения графика.')",
        "    else:",
    ]

    if uses_palette:
        palette = view.get("palette") or ["#0ea5e9", "#8b5cf6"]
        color_field_value = y_value if color_mode == "gradient" else x_value
        color_type = "Q" if color_mode == "gradient" else "N"
        color_field = python_string_literal(
            f"{color_field_value}:{color_type}"
        )
        mark = (
            "mark_bar(cornerRadiusTopLeft=5, cornerRadiusTopRight=5)"
            if view.get("type") == "bar_chart"
            else "mark_circle(size=85, opacity=0.82)"
        )
        lines.extend([
            f"        builder_chart = alt.Chart(chart_df).{mark}.encode(",
            f"            x=alt.X({x}, title={x}, sort=None),",
            f"            y=alt.Y({y}, title={y}),",
            "            color=alt.Color(",
            f"                {color_field},",
            f"                scale=alt.Scale(range={palette!r}),",
            f"                legend=alt.Legend(title={python_string_literal(color_field_value)}),",
            "            ),",
            "            tooltip=[",
            f"                alt.Tooltip({x}, title={x}),",
            f"                alt.Tooltip({y}, title={y}),",
            "            ],",
            "        )",
        ])
        if view.get("type") == "scatter_plot":
            lines.append("        builder_chart = builder_chart.interactive()")
        lines.extend([
            f"        builder_chart = builder_chart.properties(height={height})",
            "        st.altair_chart(builder_chart, width='stretch')",
        ])
    else:
        lines.append(
            f"        st.{chart_method}(chart_df, x={x}, y={y}, color={color}, height={height}, width='stretch')"
        )

    return lines


def render_code_metric(view: dict) -> list[str]:
    title = python_string_literal(view.get("title"), "Метрика")
    field_value = view.get("field")
    field = python_string_literal(field_value)
    description_value = view.get("description", "")
    description = python_string_literal(description_value)
    aggregation = python_string_literal(view.get("aggregation"), "sum")
    height = get_component_height(view, 200)
    missing_warning = python_string_literal(
        f"Колонка «{field_value}» не найдена для метрики."
    )

    lines = [
        "try:",
        f"    metric_value = calculate_metric(filtered_df, {field}, {aggregation})",
        "except KeyError:",
        f"    st.warning({missing_warning})",
        "except ValueError as error:",
        "    st.warning(str(error))",
        "else:",
        f"    st.metric({title}, metric_value, height={height})",
    ]

    if description_value:
        lines.append(f"    st.caption({description})")

    return lines
