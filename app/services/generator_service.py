from app.services.renderers.export_render import render_export_dashboard_code
from app.utils.schema_utils import (
    get_dashboard_title,
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
    data_sources = [
        {
            "datasetId": ds.get("datasetId") or "default",
            "name": ds.get("name") or "data.csv",
        }
        for ds in schema.get("dataSources", [])
    ]

    return [
        "DATA_DIR = Path(__file__).parent / 'data'",
        f"DATA_SOURCES = {data_sources!r}",
        "",
        "@st.cache_data(show_spinner=False)",
        "def load_dataset(path):",
        "    return pd.read_csv(path, low_memory=False)",
        "",
        "datasets = {}",
        "for source in DATA_SOURCES:",
        "    data_path = DATA_DIR / source['name']",
        "    if not data_path.exists():",
        "        st.error(f'CSV файл не найден: {data_path}')",
        "        st.stop()",
        "    try:",
        "        datasets[source['datasetId']] = load_dataset(str(data_path))",
        "    except Exception as e:",
        "        st.error(f'Ошибка чтения CSV ({source[\"name\"]}): {e}')",
        "        st.stop()",
        "",
    ]


def generate_streamlit_code(schema: dict) -> str:
    code: list[str] = []

    code.extend(generate_imports())
    code.extend(generate_dashboard_header(schema))
    code.extend(generate_dataframe_setup(schema))
    code.extend(render_export_dashboard_code(schema))

    return "\n".join(code)