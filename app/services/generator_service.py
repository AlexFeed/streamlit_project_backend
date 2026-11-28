import io
import zipfile
from pathlib import Path

from app.services import dataset_service
from app.services.renderers.export_render import render_export_dashboard_code
from app.utils.schema_utils import (
    get_dashboard_title,
    python_string_literal,
)

BASE_REQUIREMENTS = "streamlit>=1.57\npandas>=2.2\n"
EXCEL_REQUIREMENTS = f"{BASE_REQUIREMENTS}openpyxl>=3.1\n"

# Helpful files for users who download and run locally
EXPORT_README_MD = r"""
# Downloaded dashboard

This archive contains a generated Streamlit dashboard. To run locally:

1. Create a Python virtual environment (recommended):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1  # PowerShell
# or .venv\Scripts\activate  # CMD
```

2. Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

3. Run the app:

```powershell
python -m streamlit run app.py --server.port 8501
```

If you prefer a one-click script, use `run_local.bat` (Windows) or `run_local.sh` (Linux/macOS).
""".lstrip("\n")

EXPORT_RUN_LOCAL_BAT = """\
@echo off
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.port 8501
"""

EXPORT_RUN_LOCAL_SH = """\
#!/usr/bin/env bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.port 8501
"""


class DatasetNotFoundError(LookupError):
    """Raised when a referenced dataset does not exist for the current user."""


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
            "format": ds.get("format") or "csv",
            "delimiter": ds.get("delimiter"),
            "encoding": ds.get("encoding"),
            "sheetName": ds.get("sheetName"),
        }
        for ds in schema.get("dataSources", [])
    ]

    return [
        "DATA_DIR = Path(__file__).parent / 'data'",
        f"DATA_SOURCES = {data_sources!r}",
        "",
        "@st.cache_data(show_spinner=False)",
        "def load_dataset(path, file_format='csv', delimiter=None, encoding=None, sheet_name=None):",
        "    lower_path = str(path).lower()",
        "    if file_format == 'excel' or lower_path.endswith(('.xlsx', '.xls')):",
        "        return pd.read_excel(path, sheet_name=sheet_name or 0)",
        "    sep = delimiter if delimiter else ('\\t' if lower_path.endswith('.tsv') else ',')",
        "    return pd.read_csv(path, sep=sep, encoding=encoding, low_memory=False)",
        "",
        "datasets = {}",
        "for source in DATA_SOURCES:",
        "    data_path = DATA_DIR / source['name']",
        "    if not data_path.exists():",
        "        st.error(f'Data file not found: {data_path}')",
        "        st.stop()",
        "    try:",
        "        datasets[source['datasetId']] = load_dataset(str(data_path), file_format=source.get('format'), delimiter=source.get('delimiter'), encoding=source.get('encoding'), sheet_name=source.get('sheetName'))",
        "    except Exception as e:",
        "        st.error(f'Failed to read file ({source[\"name\"]}): {e}')",
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


def _build_requirements_txt(dataset_files: list[tuple[Path, str]]) -> str:
    has_excel = any(
        file_name.lower().endswith((".xlsx", ".xls"))
        for _, file_name in dataset_files
    )
    return EXCEL_REQUIREMENTS if has_excel else BASE_REQUIREMENTS


def build_dashboard_zip(user_id: str, schema: dict) -> io.BytesIO:
    data_sources = schema.get("dataSources") or []
    if not data_sources:
        raise ValueError("dataSources are required")

    used_names: set[str] = set()
    dataset_files: list[tuple[Path, str]] = []
    export_sources: list[dict] = []

    for ds in data_sources:
        dataset_id = ds.get("datasetId")
        if not dataset_id:
            raise ValueError("datasetId is required")

        dataset_path = dataset_service.get_dataset_path(user_id, dataset_id)
        dataset_meta = dataset_service.get_dataset_meta(user_id, dataset_id)
        if not dataset_path or not dataset_meta:
            raise DatasetNotFoundError("Dataset not found")

        file_name = dataset_meta["name"]
        if file_name in used_names:
            file_name = f"{dataset_id}_{file_name}"
        used_names.add(file_name)

        export_sources.append({**ds, "name": file_name})
        dataset_files.append((dataset_path, file_name))

    code = generate_streamlit_code({**schema, "dataSources": export_sources})

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("app.py", code)
        for dataset_path, file_name in dataset_files:
            zip_file.write(dataset_path, f"data/{file_name}")
        zip_file.writestr("requirements.txt", _build_requirements_txt(dataset_files))
        zip_file.writestr("README.md", EXPORT_README_MD)
        zip_file.writestr("run_local.bat", EXPORT_RUN_LOCAL_BAT)
        zip_file.writestr("run_local.sh", EXPORT_RUN_LOCAL_SH)

    buffer.seek(0)
    return buffer
