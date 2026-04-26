from app.services.renderers.schema_utils import (
    get_filters,
    get_views,
    safe_string,
    safe_variable_name,
)


# Render финального кода для скачивания файлом
def render_code_dashboard(schema: dict) -> list[str]:
    lines: list[str] = []

    lines.extend(render_code_filters(schema))
    lines.extend(render_code_views(schema))

    return lines


def render_code_filters(schema: dict) -> list[str]:
    filters = get_filters(schema)

    if not filters:
        return []

    lines = [
        "st.subheader('Фильтры')",
        "",
    ]

    for flt in filters:
        if flt.get("type") == "selectbox":
            lines.extend(render_code_selectbox(flt))

    return lines


def render_code_selectbox(flt: dict) -> list[str]:
    title = safe_string(flt.get("title"), "Фильтр")
    field = safe_string(flt.get("field"), "")

    if not field:
        return []

    variable_name = f"selected_{safe_variable_name(field)}"

    return [
        f"if '{field}' in df.columns:",
        f"    {variable_name} = st.selectbox(",
        f"        '{title}',",
        f"        ['Все'] + sorted(df['{field}'].dropna().astype(str).unique().tolist()),",
        "    )",
        "",
        f"    if {variable_name} != 'Все':",
        f"        filtered_df = filtered_df[filtered_df['{field}'].astype(str) == {variable_name}]",
        "else:",
        f"    st.warning(\"Колонка '{field}' не найдена для фильтра.\")",
        "",
    ]


def render_code_views(schema: dict) -> list[str]:
    views = get_views(schema)
    lines: list[str] = []

    for view in views:
        view_type = view.get("type")

        if view_type == "line_chart":
            lines.extend(render_code_line_chart(view))

        elif view_type == "bar_chart":
            lines.extend(render_code_bar_chart(view))

        elif view_type == "metric":
            lines.extend(render_code_metric(view))

    return lines


def render_code_line_chart(view: dict) -> list[str]:
    title = safe_string(view.get("title"), "Линейный график")
    x = safe_string(view.get("x"), "")
    y = safe_string(view.get("y"), "")

    if not x or not y:
        return []

    return [
        f"st.subheader('{title}')",
        f"if '{x}' in filtered_df.columns and '{y}' in filtered_df.columns:",
        f"    chart_df = filtered_df[['{x}', '{y}']].dropna().copy()",
        "    if not chart_df.empty:",
        f"        st.line_chart(chart_df.set_index('{x}')['{y}'])",
        "    else:",
        "        st.info('Нет данных для отображения графика.')",
        "else:",
        f"    st.warning(\"Колонки '{x}' и/или '{y}' не найдены.\")",
        "",
    ]


def render_code_bar_chart(view: dict) -> list[str]:
    title = safe_string(view.get("title"), "Столбчатый график")
    x = safe_string(view.get("x"), "")
    y = safe_string(view.get("y"), "")

    if not x or not y:
        return []

    return [
        f"st.subheader('{title}')",
        f"if '{x}' in filtered_df.columns and '{y}' in filtered_df.columns:",
        f"    chart_df = filtered_df[['{x}', '{y}']].dropna().copy()",
        "    if not chart_df.empty:",
        f"        st.bar_chart(chart_df.set_index('{x}')['{y}'])",
        "    else:",
        "        st.info('Нет данных для отображения графика.')",
        "else:",
        f"    st.warning(\"Колонки '{x}' и/или '{y}' не найдены.\")",
        "",
    ]


def render_code_metric(view: dict) -> list[str]:
    title = safe_string(view.get("title"), "Метрика")
    field = safe_string(view.get("field"), "")
    description = safe_string(view.get("description"), "")

    if not field:
        return []

    lines = [
        f"st.subheader('{title}')",
        f"if '{field}' in filtered_df.columns:",
        f"    metric_value = filtered_df['{field}'].sum()",
        f"    st.metric(label='{title}', value=metric_value)",
    ]

    if description:
        lines.append(f"    st.caption('{description}')")

    lines.extend([
        "else:",
        f"    st.warning(\"Колонка '{field}' не найдена для метрики.\")",
        "",
    ])

    return lines