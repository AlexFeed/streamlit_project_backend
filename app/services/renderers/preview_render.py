import os

import pandas as pd
import requests
import streamlit as st

from render_core import render_dashboard

# Весь код внутри этого файла запускается на сервере для отображения streamlit приложения без скачивания zip-архива

API_BASE = os.getenv(
    "STREAMLIT_BUILDER_API_BASE",
    "http://localhost:8000",
).rstrip("/")

st.set_page_config(
    page_title="Streamlit Builder Preview",
    page_icon="📊",
    layout="wide",
)

# Получение id превью сессии
params = st.query_params
session_id = params.get("session_id")

if not session_id:
    st.error("No preview session")
    st.stop()

# Получение данных по проекту по id сессии
try:
    response = requests.get(
        f"{API_BASE}/preview/{session_id}",
        timeout=10,
    )
except requests.RequestException as error:
    st.error(f"Backend preview недоступен: {error}")
    st.stop()

if response.status_code != 200:
    st.error("Preview session not found")
    st.stop()

data = response.json()
schema = data["schema"]
datasets_paths = data.get("datasetsPaths") or {}


# Кэширование загруженных источников данных
@st.cache_data(show_spinner=False)
def load_dataset(path: str, file_format: str | None = None, delimiter: str | None = None, sheet_name: str | None = None):
    lower_path = path.lower()
    if file_format == "excel" or lower_path.endswith((".xlsx", ".xls")):
        return pd.read_excel(path, sheet_name=sheet_name or 0)

    sep = delimiter if delimiter else ("\t" if lower_path.endswith(".tsv") else ",")
    return pd.read_csv(path, sep=sep, low_memory=False)


data_sources_by_id = {
    ds.get("datasetId"): ds
    for ds in schema.get("dataSources", [])
    if ds.get("datasetId")
}

datasets = {}
for ds_id, file_path in datasets_paths.items():
    ds_config = data_sources_by_id.get(ds_id, {})
    try:
        datasets[ds_id] = load_dataset(
            file_path,
            file_format=ds_config.get("format"),
            delimiter=ds_config.get("delimiter"),
            sheet_name=ds_config.get("sheetName"),
        )
    except Exception as error:
        display_name = ds_config.get("name") or ds_id
        st.error(f"Ошибка чтения данных ({display_name}): {error}")
        st.stop()

dashboard_title = schema.get("dashboard", {}).get("title") or "Streamlit Dashboard"
st.title(dashboard_title)
st.caption("Интерактивный дашборд, созданный в Streamlit Builder")

# Вызов функции-генератора всего streamlit кода
render_dashboard(schema, datasets)