import streamlit as st

from app.services.renderers.schema_utils import (
    get_dashboard_title,
    get_filters,
    get_views,
)

# Runtime render дашборда (генерация кода для preview mode)

def render_runtime_dashboard(schema: dict, df):
    filtered_df = df.copy()

    st.title(get_dashboard_title(schema))

    filtered_df = render_runtime_filters(schema, df, filtered_df)
    render_runtime_views(schema, filtered_df)


def render_runtime_filters(schema: dict, df, filtered_df):
    filters = get_filters(schema)

    if not filters:
        return filtered_df

    st.subheader("Фильтры")

    for flt in filters:
        if flt.get("type") != "selectbox":
            continue

        field = flt.get("field")
        title = flt.get("title", "Фильтр")

        if not field or field not in df.columns:
            st.warning(f"Колонка '{field}' не найдена для фильтра.")
            continue

        selected = st.selectbox(
            title,
            ["Все"] + sorted(df[field].dropna().astype(str).unique().tolist()),
            )

        if selected != "Все":
            filtered_df = filtered_df[
                filtered_df[field].astype(str) == selected
                ]

    return filtered_df


def render_runtime_views(schema: dict, filtered_df):
    views = get_views(schema)

    for view in views:
        view_type = view.get("type")

        if view_type == "line_chart":
            render_runtime_line_chart(view, filtered_df)

        elif view_type == "bar_chart":
            render_runtime_bar_chart(view, filtered_df)

        elif view_type == "metric":
            render_runtime_metric(view, filtered_df)


def render_runtime_line_chart(view: dict, filtered_df):
    title = view.get("title", "Линейный график")
    x = view.get("x")
    y = view.get("y")

    st.subheader(title)

    if not x or not y or x not in filtered_df.columns or y not in filtered_df.columns:
        st.warning(f"Колонки '{x}' и/или '{y}' не найдены.")
        return

    chart_df = filtered_df[[x, y]].dropna().copy()

    if chart_df.empty:
        st.info("Нет данных для отображения графика.")
        return

    st.line_chart(chart_df.set_index(x)[y])


def render_runtime_bar_chart(view: dict, filtered_df):
    title = view.get("title", "Столбчатый график")
    x = view.get("x")
    y = view.get("y")

    st.subheader(title)

    if not x or not y or x not in filtered_df.columns or y not in filtered_df.columns:
        st.warning(f"Колонки '{x}' и/или '{y}' не найдены.")
        return

    chart_df = filtered_df[[x, y]].dropna().copy()

    if chart_df.empty:
        st.info("Нет данных для отображения графика.")
        return

    st.bar_chart(chart_df.set_index(x)[y])


def render_runtime_metric(view: dict, filtered_df):
    title = view.get("title", "Метрика")
    field = view.get("field")
    description = view.get("description", "")

    if not field or field not in filtered_df.columns:
        st.warning(f"Колонка '{field}' не найдена для метрики.")
        return

    st.metric(title, filtered_df[field].sum())

    if description:
        st.caption(description)