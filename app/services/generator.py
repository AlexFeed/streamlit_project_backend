# app/services/generator.py


# =========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================

def safe_string(value: str | None, fallback: str = "") -> str:
    """
    Подготавливает строку для безопасной вставки в генерируемый Python-код.
    """
    if value is None:
        return fallback

    return str(value).replace("'", "\\'")


def safe_variable_name(value: str) -> str:
    """
    Преобразует название поля в безопасное имя переменной Python.
    Например: 'product-category' -> 'product_category'
    """
    result = str(value)

    for symbol in [" ", "-", ".", ",", ":", ";", "/", "\\"]:
        result = result.replace(symbol, "_")

    return result


# =========================
# БАЗОВЫЕ БЛОКИ КОДА
# =========================

def generate_imports() -> list[str]:
    """
    Генерирует импорты для итогового Streamlit-приложения.
    """
    return [
        "from pathlib import Path",
        "",
        "import pandas as pd",
        "import streamlit as st",
        "",
    ]


def generate_dashboard_header(schema: dict) -> list[str]:
    """
    Генерирует заголовок дашборда.
    """
    title = safe_string(
        schema.get("dashboard", {}).get("title"),
        "Generated Dashboard",
    )

    return [
        f"st.title('{title}')",
        "",
    ]


def generate_dataframe_setup(schema: dict) -> list[str]:
    """
    Генерирует код загрузки CSV из папки data рядом с app.py.
    """
    dataset_name = safe_string(
        schema.get("dataSource", {}).get("name"),
        "data.csv",
    )

    return [
        f"DATA_PATH = Path(__file__).parent / 'data' / '{dataset_name}'",
        "",
        "if not DATA_PATH.exists():",
        "    st.error(f'CSV файл не найден: {DATA_PATH}')",
        "    st.stop()",
        "",
        "try:",
        "    df = pd.read_csv(DATA_PATH)",
        "except Exception as e:",
        "    st.error(f'Ошибка чтения CSV: {e}')",
        "    st.stop()",
        "",
        "filtered_df = df.copy()",
        "",
    ]


# =========================
# ФИЛЬТРЫ
# =========================

def generate_selectbox_filter(component: dict) -> list[str]:
    """
    Генерирует selectbox как глобальный фильтр для всего filtered_df.
    """
    title = safe_string(
        component.get("config", {}).get("title"),
        "Фильтр",
    )

    field = safe_string(
        component.get("bindings", {}).get("field"),
        "",
    )

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
        f"    st.warning(\"Колонка '{field}' не найдена в датасете.\")",
        "",
    ]


def generate_global_filters(components: list[dict]) -> list[str]:
    """
    Генерирует блок глобальных фильтров.
    Все selectbox-компоненты применяются к одному общему filtered_df.
    """
    filter_components = [
        component
        for component in components
        if component.get("type") == "selectbox"
    ]

    if not filter_components:
        return []

    lines = [
        "st.subheader('Фильтры')",
        "",
    ]

    for component in filter_components:
        lines.extend(generate_selectbox_filter(component))

    return lines


# =========================
# ВИЗУАЛЬНЫЕ КОМПОНЕНТЫ
# =========================

def generate_line_chart(component: dict) -> list[str]:
    """
    Генерирует линейный график.
    """
    title = safe_string(
        component.get("config", {}).get("title"),
        "Линейный график",
    )

    x_field = safe_string(
        component.get("bindings", {}).get("xField"),
        "",
    )

    y_field = safe_string(
        component.get("bindings", {}).get("yField"),
        "",
    )

    if not x_field or not y_field:
        return []

    return [
        f"st.subheader('{title}')",
        f"if '{x_field}' in filtered_df.columns and '{y_field}' in filtered_df.columns:",
        f"    chart_df = filtered_df[['{x_field}', '{y_field}']].dropna().copy()",
        "",
        "    if not chart_df.empty:",
        f"        chart_df = chart_df.set_index('{x_field}')",
        f"        st.line_chart(chart_df['{y_field}'])",
        "    else:",
        "        st.info('Нет данных для отображения линейного графика.')",
        "else:",
        f"    st.warning(\"Колонки '{x_field}' и/или '{y_field}' не найдены.\")",
        "",
    ]


def generate_bar_chart(component: dict) -> list[str]:
    """
    Генерирует столбчатый график.
    """
    title = safe_string(
        component.get("config", {}).get("title"),
        "Столбчатый график",
    )

    x_field = safe_string(
        component.get("bindings", {}).get("xField"),
        "",
    )

    y_field = safe_string(
        component.get("bindings", {}).get("yField"),
        "",
    )

    if not x_field or not y_field:
        return []

    return [
        f"st.subheader('{title}')",
        f"if '{x_field}' in filtered_df.columns and '{y_field}' in filtered_df.columns:",
        f"    chart_df = filtered_df[['{x_field}', '{y_field}']].dropna().copy()",
        "",
        "    if not chart_df.empty:",
        f"        chart_df = chart_df.set_index('{x_field}')",
        f"        st.bar_chart(chart_df['{y_field}'])",
        "    else:",
        "        st.info('Нет данных для отображения столбчатого графика.')",
        "else:",
        f"    st.warning(\"Колонки '{x_field}' и/или '{y_field}' не найдены.\")",
        "",
    ]


def generate_metric(component: dict) -> list[str]:
    """
    Генерирует метрику.
    Для MVP используется сумма по выбранной колонке.
    """
    title = safe_string(
        component.get("config", {}).get("title"),
        "Метрика",
    )

    description = safe_string(
        component.get("config", {}).get("description"),
        "",
    )

    value_field = safe_string(
        component.get("bindings", {}).get("valueField"),
        "",
    )

    if not value_field:
        return []

    lines = [
        f"st.subheader('{title}')",
        f"if '{value_field}' in filtered_df.columns:",
        f"    metric_value = filtered_df['{value_field}'].sum()",
        f"    st.metric(label='{title}', value=metric_value)",
    ]

    if description:
        lines.append(f"    st.caption('{description}')")

    lines.extend([
        "else:",
        f"    st.warning(\"Колонка '{value_field}' не найдена.\")",
        "",
    ])

    return lines


def generate_visual_components(components: list[dict]) -> list[str]:
    """
    Генерирует все визуальные компоненты кроме фильтров.
    """
    lines: list[str] = []

    visual_components = [
        component
        for component in components
        if component.get("type") != "selectbox"
    ]

    for component in visual_components:
        component_type = component.get("type")

        if component_type == "line_chart":
            lines.extend(generate_line_chart(component))

        elif component_type == "bar_chart":
            lines.extend(generate_bar_chart(component))

        elif component_type == "metric":
            lines.extend(generate_metric(component))

    return lines


# =========================
# ОСНОВНАЯ ФУНКЦИЯ
# =========================

def generate_streamlit_code(schema: dict) -> str:
    """
    Главная функция генерации Streamlit-кода.

    Порядок:
    1. Импорты
    2. Заголовок
    3. Загрузка CSV из папки data
    4. Глобальные фильтры
    5. Визуальные компоненты
    """
    components = sorted(
        schema.get("components", []),
        key=lambda item: item.get("order", 0),
    )

    code: list[str] = []

    code.extend(generate_imports())
    code.extend(generate_dashboard_header(schema))
    code.extend(generate_dataframe_setup(schema))
    code.extend(generate_global_filters(components))
    code.extend(generate_visual_components(components))

    return "\n".join(code)