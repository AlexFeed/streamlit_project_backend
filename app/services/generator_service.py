from app.services.renderers.elements_export_render import (
    render_elements_dashboard_code,
)
from app.services.renderers.schema_utils import (
    get_dashboard_title,
    get_dataset_name,
    python_string_literal,
)


def generate_imports() -> list[str]:
    return [
        "from pathlib import Path",
        "",
        "import pandas as pd",
        "import streamlit as st",
        "from streamlit_elements import dashboard, elements, mui, nivo",
        "",
    ]


def generate_dashboard_header(schema: dict) -> list[str]:
    title = python_string_literal(
        get_dashboard_title(schema),
        "Generated Dashboard",
    )

    return [
        f"st.set_page_config(page_title={title}, layout='wide')",
        f"st.title({title})",
        "st.caption('Интерактивный дашборд, созданный в Streamlit Builder')",
        "",
    ]


def generate_dataframe_setup(schema: dict) -> list[str]:
    dataset_name = python_string_literal(get_dataset_name(schema), "data.csv")

    return [
        f"DATA_PATH = Path(__file__).parent / 'data' / {dataset_name}",
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


def generate_data_helpers() -> list[str]:
    return [
        "SUPPORTED_AGGREGATIONS = {'none', 'sum', 'mean', 'count', 'min', 'max'}",
        "SUPPORTED_SORT_ORDERS = {'none', 'asc', 'desc'}",
        "SUPPORTED_SORT_FIELDS = {'x', 'y'}",
        "",
        "def prepare_chart_data(dataframe, x, y, aggregation='none', sort_order='none', sort_by='x'):",
        "    if not x or not y:",
        "        raise ValueError('Для графика должны быть выбраны поля X и Y')",
        "    missing_fields = [field for field in (x, y) if field not in dataframe.columns]",
        "    if missing_fields:",
        "        raise KeyError(', '.join(missing_fields))",
        "    if aggregation not in SUPPORTED_AGGREGATIONS:",
        "        raise ValueError(f'Неизвестная агрегация: {aggregation}')",
        "    if sort_order not in SUPPORTED_SORT_ORDERS:",
        "        raise ValueError(f'Неизвестная сортировка: {sort_order}')",
        "    if sort_by not in SUPPORTED_SORT_FIELDS:",
        "        raise ValueError(f'Неизвестное поле сортировки: {sort_by}')",
        "    chart_df = dataframe[[x, y]].dropna().copy()",
        "    if chart_df.empty:",
        "        return chart_df",
        "    if aggregation != 'count':",
        "        chart_df[y] = pd.to_numeric(chart_df[y], errors='coerce')",
        "        chart_df = chart_df.dropna(subset=[y])",
        "    if aggregation != 'none':",
        "        chart_df = chart_df.groupby(x, as_index=False, dropna=False)[y].agg(aggregation)",
        "    if sort_order != 'none':",
        "        sort_column = y if sort_by == 'y' else x",
        "        chart_df = chart_df.sort_values(by=sort_column, ascending=sort_order == 'asc', kind='stable')",
        "    return chart_df",
        "",
        "def calculate_metric(dataframe, field, aggregation='sum'):",
        "    if not field or field not in dataframe.columns:",
        "        raise KeyError(field)",
        "    if aggregation == 'count':",
        "        return int(dataframe[field].count())",
        "    if aggregation not in SUPPORTED_AGGREGATIONS - {'none'}:",
        "        raise ValueError(f'Неизвестная агрегация: {aggregation}')",
        "    values = pd.to_numeric(dataframe[field], errors='coerce').dropna()",
        "    if values.empty:",
        "        return 0",
        "    result = values.agg(aggregation)",
        "    return result.item() if hasattr(result, 'item') else result",
        "",
    ]


def generate_streamlit_code(schema: dict) -> str:
    code: list[str] = []

    code.extend(generate_imports())
    code.extend(generate_dashboard_header(schema))
    code.extend(generate_data_helpers())
    code.extend(generate_dataframe_setup(schema))
    code.extend(render_elements_dashboard_code(schema))

    return "\n".join(code)
