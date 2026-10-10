from app.services.renderers.native_export_render import render_native_dashboard_code
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
        "@st.cache_data(show_spinner=False)",
        "def load_dataset(path):",
        "    return pd.read_csv(path, low_memory=False)",
        "",
        "try:",
        "    df = load_dataset(str(DATA_PATH))",
        "except Exception as e:",
        "    st.error(f'Ошибка чтения CSV: {e}')",
        "    st.stop()",
        "",
    ]


def generate_streamlit_code(schema: dict) -> str:
    code: list[str] = []

    code.extend(generate_imports())
    code.extend(generate_dashboard_header(schema))
    code.extend(generate_dataframe_setup(schema))
    code.extend(render_native_dashboard_code(schema))

    return "\n".join(code)
