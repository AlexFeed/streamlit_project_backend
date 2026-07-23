import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import UploadFile
from pandas.api.types import (
    is_bool_dtype,
    is_datetime64_any_dtype,
    is_numeric_dtype,
)

# Загрузка dataset на бэкенд и извлечение мета данных (названий колонок)

DATASETS_DIR = Path("storage/datasets")


def _infer_field_type(series) -> str:
    if is_bool_dtype(series):
        return "boolean"
    if is_numeric_dtype(series):
        return "number"
    if is_datetime64_any_dtype(series):
        return "datetime"

    non_empty = series.dropna()
    if not non_empty.empty:
        parsed_dates = pd.to_datetime(
            non_empty,
            errors="coerce",
            format="mixed",
        )
        if parsed_dates.notna().mean() >= 0.9:
            return "datetime"

    return "string"


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _dataset_dir(user_id: str, dataset_id: str) -> Path:
    return DATASETS_DIR / user_id / dataset_id


def _data_file(user_id: str, dataset_id: str) -> Path:
    return _dataset_dir(user_id, dataset_id) / "data.csv"


def _meta_file(user_id: str, dataset_id: str) -> Path:
    return _dataset_dir(user_id, dataset_id) / "meta.json"


def save_dataset(user_id: str, file: UploadFile) -> dict:
    dataset_id = str(uuid.uuid4())

    dataset_dir = _dataset_dir(user_id, dataset_id)
    dataset_dir.mkdir(parents=True, exist_ok=True)

    data_path = dataset_dir / "data.csv"
    meta_path = dataset_dir / "meta.json"

    with data_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        df = pd.read_csv(data_path, nrows=100)
    except Exception as error:
        shutil.rmtree(dataset_dir)
        raise ValueError(f"Failed to read CSV: {error}")

    meta = {
        "datasetId": dataset_id,
        "userId": user_id,
        "name": file.filename,
        "storedName": "data.csv",
        "fields": list(df.columns),
        "fieldTypes": {
            field: _infer_field_type(df[field])
            for field in df.columns
        },
        "sampleRows": json.loads(
            df.head(20).to_json(orient="records", date_format="iso")
        ),
        "size": data_path.stat().st_size,
        "createdAt": _now(),
    }

    with meta_path.open("w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return meta


def get_dataset_meta(user_id: str, dataset_id: str) -> dict | None:
    path = _meta_file(user_id, dataset_id)

    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def get_dataset_path(user_id: str, dataset_id: str) -> Path | None:
    path = _data_file(user_id, dataset_id)

    if not path.exists():
        return None

    return path


def get_dataset_preview(
        user_id: str,
        dataset_id: str,
        limit: int = 500,
) -> dict | None:
    path = get_dataset_path(user_id, dataset_id)
    if not path:
        return None

    safe_limit = max(1, min(limit, 1000))

    try:
        dataframe = pd.read_csv(path, nrows=safe_limit)
    except Exception as error:
        raise ValueError(f"Failed to read CSV: {error}")

    return {
        "datasetId": dataset_id,
        "fields": list(dataframe.columns),
        "fieldTypes": {
            field: _infer_field_type(dataframe[field])
            for field in dataframe.columns
        },
        "rows": json.loads(
            dataframe.to_json(orient="records", date_format="iso")
        ),
        "returnedRows": len(dataframe),
        "limit": safe_limit,
    }


def delete_dataset(user_id: str, dataset_id: str) -> bool:
    dataset_dir = _dataset_dir(user_id, dataset_id)

    if not dataset_dir.exists():
        return False

    shutil.rmtree(dataset_dir)
    return True
