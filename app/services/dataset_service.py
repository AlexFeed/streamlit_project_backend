import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import UploadFile

# Загрузка dataset на бэкенд и извлечение мета данных (названий колонок)

DATASETS_DIR = Path("storage/datasets")


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
        df = pd.read_csv(data_path, nrows=5)
    except Exception as error:
        shutil.rmtree(dataset_dir)
        raise ValueError(f"Failed to read CSV: {error}")

    meta = {
        "datasetId": dataset_id,
        "userId": user_id,
        "name": file.filename,
        "storedName": "data.csv",
        "fields": list(df.columns),
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


def delete_dataset(user_id: str, dataset_id: str) -> bool:
    dataset_dir = _dataset_dir(user_id, dataset_id)

    if not dataset_dir.exists():
        return False

    shutil.rmtree(dataset_dir)
    return True