import requests
import streamlit as st
import pandas as pd
from pathlib import Path

from app.services.renderers.preview_runtime_render import render_runtime_dashboard

API_BASE = "http://localhost:8000"

params = st.query_params
session_id = params.get("session_id")

if not session_id:
    st.error("No preview session")
    st.stop()

response = requests.get(f"{API_BASE}/preview/{session_id}")

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