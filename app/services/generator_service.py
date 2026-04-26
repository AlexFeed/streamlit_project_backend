from app.services.renderers.export_code_render import render_code_dashboard
from app.services.renderers.schema_utils import (
    get_dashboard_title,
    get_dataset_name,
    safe_string,
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
    title = safe_string(get_dashboard_title(schema), "Generated Dashboard")

    return [
        f"st.title('{title}')",
        "",
    ]


def generate_dataframe_setup(schema: dict) -> list[str]:
    dataset_name = safe_string(get_dataset_name(schema), "data.csv")

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


def generate_streamlit_code(schema: dict) -> str:
    code: list[str] = []

    code.extend(generate_imports())
    code.extend(generate_dashboard_header(schema))
    code.extend(generate_dataframe_setup(schema))
    code.extend(render_code_dashboard(schema))

    return "\n".join(code)