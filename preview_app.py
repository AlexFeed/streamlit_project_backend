import requests
import streamlit as st
import pandas as pd
from pathlib import Path

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

df = pd.read_csv(dataset_path)
filtered_df = df.copy()

st.title(schema.get("dashboard", {}).get("title", "Dashboard"))

filters = schema.get("filters", [])
views = schema.get("views", [])

# Фильтры
for flt in filters:
    if flt.get("type") == "selectbox":
        field = flt.get("field")
        title = flt.get("title", "Фильтр")

        if not field or field not in df.columns:
            st.warning(f"Колонка '{field}' не найдена для фильтра.")
            continue

        selected = st.selectbox(
            title,
            ["Все"] + sorted(df[field].dropna().astype(str).unique().tolist())
        )

        if selected != "Все":
            filtered_df = filtered_df[
                filtered_df[field].astype(str) == selected
                ]

# Визуализация
for view in views:
    view_type = view.get("type")

    if view_type == "line_chart":
        x = view.get("x")
        y = view.get("y")
        title = view.get("title", "Линейный график")

        if x in filtered_df.columns and y in filtered_df.columns:
            st.subheader(title)
            chart_df = filtered_df[[x, y]].dropna().copy()

            if not chart_df.empty:
                st.line_chart(chart_df.set_index(x)[y])
            else:
                st.info("Нет данных для отображения графика.")
        else:
            st.warning(f"Колонки '{x}' и/или '{y}' не найдены.")

    elif view_type == "bar_chart":
        x = view.get("x")
        y = view.get("y")
        title = view.get("title", "Столбчатый график")

        if x in filtered_df.columns and y in filtered_df.columns:
            st.subheader(title)
            chart_df = filtered_df[[x, y]].dropna().copy()

            if not chart_df.empty:
                st.bar_chart(chart_df.set_index(x)[y])
            else:
                st.info("Нет данных для отображения графика.")
        else:
            st.warning(f"Колонки '{x}' и/или '{y}' не найдены.")

    elif view_type == "metric":
        field = view.get("field")
        title = view.get("title", "Метрика")
        description = view.get("description", "")

        if field in filtered_df.columns:
            st.metric(title, filtered_df[field].sum())

            if description:
                st.caption(description)
        else:
            st.warning(f"Колонка '{field}' не найдена для метрики.")