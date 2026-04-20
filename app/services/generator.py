# =========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================

def indent(lines: list[str], level: int = 1) -> list[str]:
    """
    Добавляет отступы (4 пробела * level) к каждой строке.
    Используется для вложенных блоков, например внутри if uploaded_file is not None.
    """
    prefix = "    " * level
    return [f"{prefix}{line}" if line else "" for line in lines]


def safe_string(value: str | None, fallback: str = "") -> str:
    """
    Защищает строку для вставки в Python-код:
    - если None → подставляет fallback
    - экранирует одинарные кавычки
    """
    if value is None:
        return fallback
    return str(value).replace("'", "\\'")


# =========================
# БАЗОВЫЕ БЛОКИ КОДА
# =========================

def generate_imports() -> list[str]:
    """
    Генерирует импорт библиотек для Streamlit-приложения.
    """
    return [
        "import streamlit as st",
        "import pandas as pd",
        "",
    ]


def generate_dashboard_header(schema: dict) -> list[str]:
    """
    Генерирует заголовок страницы (st.title).
    Берётся из schema.dashboard.title.
    """
    title = safe_string(schema.get("dashboard", {}).get("title"), "Generated Dashboard")
    return [
        f"st.title('{title}')",
        "",
    ]


def generate_file_loader() -> list[str]:
    """
    Генерирует загрузчик CSV-файла.
    Весь остальной код будет выполняться внутри условия if uploaded_file is not None.
    """
    return [
        "uploaded_file = st.file_uploader('Загрузите CSV файл', type=['csv'])",
        "",
        "if uploaded_file is not None:",
    ]


def generate_dataframe_setup() -> list[str]:
    """
    Генерирует код чтения CSV и создания filtered_df.
    filtered_df — это копия df, к которой будут применяться фильтры.
    """
    return [
        "try:",
        "    df = pd.read_csv(uploaded_file)",
        "except Exception as e:",
        "    st.error(f'Ошибка чтения CSV: {e}')",
        "    st.stop()",
        "",
        "filtered_df = df.copy()",
        "",
    ]


# =========================
# ФИЛЬТРЫ (SELECTBOX)
# =========================

def generate_selectbox_filter(component: dict) -> list[str]:
    """
    Генерирует один selectbox-фильтр.

    Логика:
    - берём колонку из bindings.field
    - создаём selectbox с уникальными значениями
    - если выбрано значение ≠ 'Все', фильтруем filtered_df
    """
    title = safe_string(component.get("config", {}).get("title"), "Фильтр")
    field = safe_string(component.get("bindings", {}).get("field"), "")

    if not field:
        return []

    # Имя переменной (например selected_department)
    variable_name = f"selected_{field}".replace(" ", "_").replace("-", "_")

    return [
        f"if '{field}' in df.columns:",
        f"    {variable_name} = st.selectbox(",
        f"        '{title}',",
        f"        ['Все'] + sorted(df['{field}'].dropna().astype(str).unique().tolist())",
        "    )",
        f"    if {variable_name} != 'Все':",
        f"        filtered_df = filtered_df[filtered_df['{field}'].astype(str) == {variable_name}]",
        "else:",
        f"    st.warning(\"Колонка '{field}' не найдена в датасете.\")",
        "",
    ]


def generate_global_filters(components: list[dict]) -> list[str]:
    """
    Проходит по всем компонентам и выбирает только selectbox.
    Генерирует блок фильтров (глобальных для всего DataFrame).
    """
    lines: list[str] = []

    filter_components = [c for c in components if c.get("type") == "selectbox"]
    if not filter_components:
        return lines

    lines.extend([
        "st.subheader('Фильтры')",
        "",
    ])

    for component in filter_components:
        lines.extend(generate_selectbox_filter(component))

    return lines


# =========================
# ВИЗУАЛИЗАЦИЯ
# =========================

def generate_line_chart(component: dict) -> list[str]:
    """
    Генерирует линейный график.

    Логика:
    - берём x и y поля
    - фильтруем NaN
    - делаем x индексом
    - строим st.line_chart
    """
    title = safe_string(component.get("config", {}).get("title"), "Линейный график")
    x_field = safe_string(component.get("bindings", {}).get("xField"), "")
    y_field = safe_string(component.get("bindings", {}).get("yField"), "")

    if not x_field or not y_field:
        return []

    return [
        f"st.subheader('{title}')",
        f"if '{x_field}' in filtered_df.columns and '{y_field}' in filtered_df.columns:",
        f"    chart_df = filtered_df[['{x_field}', '{y_field}']].dropna().copy()",
        "    if not chart_df.empty:",
        f"        chart_df = chart_df.set_index('{x_field}')",
        f"        st.line_chart(chart_df['{y_field}'])",
        "    else:",
        "        st.info('Нет данных для отображения.')",
        "else:",
        f"    st.warning(\"Колонки '{x_field}' или '{y_field}' не найдены.\")",
        "",
    ]


def generate_bar_chart(component: dict) -> list[str]:
    """
    Генерирует столбчатый график.
    Логика аналогична line_chart, но используется st.bar_chart.
    """
    title = safe_string(component.get("config", {}).get("title"), "Столбчатый график")
    x_field = safe_string(component.get("bindings", {}).get("xField"), "")
    y_field = safe_string(component.get("bindings", {}).get("yField"), "")

    if not x_field or not y_field:
        return []

    return [
        f"st.subheader('{title}')",
        f"if '{x_field}' in filtered_df.columns and '{y_field}' in filtered_df.columns:",
        f"    chart_df = filtered_df[['{x_field}', '{y_field}']].dropna().copy()",
        "    if not chart_df.empty:",
        f"        chart_df = chart_df.set_index('{x_field}')",
        f"        st.bar_chart(chart_df['{y_field}'])",
        "    else:",
        "        st.info('Нет данных для отображения.')",
        "else:",
        f"    st.warning(\"Колонки '{x_field}' или '{y_field}' не найдены.\")",
        "",
    ]


def generate_metric(component: dict) -> list[str]:
    """
    Генерирует метрику.

    MVP-логика:
    - берём колонку
    - считаем сумму (sum)
    - выводим st.metric
    """
    title = safe_string(component.get("config", {}).get("title"), "Метрика")
    value_field = safe_string(component.get("bindings", {}).get("valueField"), "")

    if not value_field:
        return []

    return [
        f"if '{value_field}' in filtered_df.columns:",
        f"    metric_value = filtered_df['{value_field}'].sum()",
        f"    st.metric(label='{title}', value=metric_value)",
        "else:",
        f"    st.warning(\"Колонка '{value_field}' не найдена.\")",
        "",
    ]


def generate_visual_components(components: list[dict]) -> list[str]:
    """
    Генерирует все визуальные компоненты (кроме фильтров).

    Проходит по компонентам и вызывает нужную функцию:
    - line_chart
    - bar_chart
    - metric
    """
    lines: list[str] = []

    visual_components = [c for c in components if c.get("type") != "selectbox"]

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
    Главная функция генерации.

    Шаги:
    1. Сортируем компоненты по order
    2. Генерируем базовые блоки
    3. Генерируем фильтры
    4. Генерируем визуализацию
    5. Склеиваем всё в один Python-файл
    """

    components = sorted(
        schema.get("components", []),
        key=lambda item: item.get("order", 0),
    )

    code: list[str] = []

    # Базовые блоки
    code.extend(generate_imports())
    code.extend(generate_dashboard_header(schema))
    code.extend(generate_file_loader())

    # Тело внутри if uploaded_file is not None
    body_lines: list[str] = []
    body_lines.extend(generate_dataframe_setup())
    body_lines.extend(generate_global_filters(components))
    body_lines.extend(generate_visual_components(components))

    # Добавляем отступ (внутри if)
    code.extend(indent(body_lines, level=1))

    # Поведение, если файл не загружен
    code.extend([
        "else:",
        "    st.info('Загрузите CSV файл, чтобы увидеть дашборд.')",
    ])

    return "\n".join(code)