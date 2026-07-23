import os
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

from app.services.renderers.preview_runtime_render import render_runtime_dashboard

API_BASE = os.getenv(
    "STREAMLIT_BUILDER_API_BASE",
    "http://localhost:8000",
).rstrip("/")

st.set_page_config(
    page_title="Streamlit Builder Preview",
    page_icon="📊",
    layout="wide",
)

params = st.query_params
session_id = params.get("session_id")

if not session_id:
    st.error("No preview session")
    st.stop()

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

try:
    df = pd.read_csv(dataset_path)
except Exception as error:
    st.error(f"Ошибка чтения CSV: {error}")
    st.stop()

render_runtime_dashboard(schema, df)
