import os
import sys
from pathlib import Path

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
dataset_path = Path(data["datasetPath"])


@st.cache_data(show_spinner=False)
def load_dataset(path: str):
    return pd.read_csv(path, low_memory=False)


try:
    df = load_dataset(str(dataset_path))
except Exception as error:
    st.error(f"Ошибка чтения CSV: {error}")
    st.stop()

data_sources = schema.get("dataSources") or []
dataset_id = data_sources[0].get("datasetId") if data_sources else "default"
datasets = {dataset_id: df}

dashboard_title = schema.get("dashboard", {}).get("title") or "Streamlit Dashboard"
st.title(dashboard_title)
st.caption("Интерактивный дашборд, созданный в Streamlit Builder")

# Вызов функции-генератора всего streamlit кода
render_dashboard(schema, datasets)