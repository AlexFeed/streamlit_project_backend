import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import UploadFile

# Загрузка dataset на бэкенд и извлечение мета данных (названий колонок)

BASE_DIR = Path("storage/datasets")
BASE_DIR.mkdir(parents=True, exist_ok=True)

DATA_FILENAME = "data.csv"
META_FILENAME = "meta.json"


def save_dataset(file: UploadFile) -> dict:
    if not file.filename.lower().endswith(".csv"):
        raise ValueError("Only CSV files are supported.")

    # Создание id для датасета
    dataset_id = str(uuid.uuid4())

    # Директория загруженного датасета
    dataset_dir = BASE_DIR / dataset_id
    dataset_dir.mkdir(parents=True, exist_ok=True)

    file_path = dataset_dir / DATA_FILENAME

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    df = pd.read_csv(file_path, nrows=5)

    # Извлечение мета данных из загруженного датасета
    meta = {
        "datasetId": dataset_id,
        "name": file.filename,
        "storedName": DATA_FILENAME,
        "fields": df.columns.tolist(),
        "size": file_path.stat().st_size,
        "createdAt": datetime.now().isoformat(),
    }

    with open(dataset_dir / META_FILENAME, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return meta


def get_dataset_path(dataset_id: str) -> Path | None:
    file_path = BASE_DIR / dataset_id / DATA_FILENAME
    return file_path if file_path.exists() else None


def get_dataset_meta(dataset_id: str) -> dict | None:
    meta_path = BASE_DIR / dataset_id / META_FILENAME

    if not meta_path.exists():
        return None

    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def delete_dataset(dataset_id: str) -> bool:
    dataset_dir = BASE_DIR / dataset_id

    if not dataset_dir.exists():
        return False

    shutil.rmtree(dataset_dir)
    return True