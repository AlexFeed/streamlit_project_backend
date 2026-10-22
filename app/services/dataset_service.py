import csv
import json
import re
import shutil
import uuid
from datetime import datetime, UTC
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
    return datetime.now(UTC).isoformat(timespec="seconds")


def _dataset_dir(user_id: str, dataset_id: str) -> Path:
    return DATASETS_DIR / user_id / dataset_id


def _data_file(user_id: str, dataset_id: str, filename: str = "data.csv") -> Path:
    return _dataset_dir(user_id, dataset_id) / filename


def _meta_file(user_id: str, dataset_id: str) -> Path:
    return _dataset_dir(user_id, dataset_id) / "meta.json"


def save_dataset(
        user_id: str,
        file: UploadFile,
        custom_name: str | None = None,
        delimiter: str | None = None,
        sheet_name: str | None = None,
) -> dict:
    dataset_id = str(uuid.uuid4())

    # Создание новой папки с датасетом
    dataset_dir = _dataset_dir(user_id, dataset_id)
    dataset_dir.mkdir(parents=True, exist_ok=True)

    # Берём расширение файла из оригинального названия файла
    original_filename = file.filename or "data.csv"
    ext = Path(original_filename).suffix.lower() or ".csv"

    # Берём название датасета, введённое пользователем, и очищаем от недопустимых символов
    raw_name = custom_name.strip() if custom_name and custom_name.strip() else Path(original_filename).stem
    clean_name = re.sub(r'[\\/*?:"<>|]', "_", raw_name).strip() or "dataset"
    file_name = f"{clean_name}{ext}"

    # Получаем пути к файлу данных и файлу метаданных через хелперы
    data_path = _data_file(user_id, dataset_id, file_name)
    meta_path = _meta_file(user_id, dataset_id)

    # Сохраняем физический файл на диск
    with data_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Определяем формат файла
    file_format = "excel" if ext in [".xlsx", ".xls"] else ("tsv" if ext == ".tsv" else "csv")

    try:
        if file_format == "excel":
            delimiter = None
            with pd.ExcelFile(data_path) as excel_file:
                available_sheets = excel_file.sheet_names
                if not available_sheets:
                    raise ValueError("Книга Excel не содержит листов")

                if not sheet_name or sheet_name not in available_sheets:
                    sheet_name = available_sheets[0]

                # Считываем сэмпл 100 строк для фиксации колонок и типов
                df_sample = pd.read_excel(excel_file, sheet_name=sheet_name, nrows=100)
        else:
            sheet_name = None
            if not delimiter or delimiter == "auto":
                # Автоопределение разделителя сниффером Python
                try:
                    with data_path.open("r", encoding="utf-8", errors="ignore") as f:
                        sample = "".join([f.readline() for _ in range(5)])
                        sniffed = csv.Sniffer().sniff(sample, delimiters=[",", ";", "\t", "|", " "])
                        delimiter = sniffed.delimiter
                except Exception:
                    delimiter = ","

            df_sample = pd.read_csv(data_path, sep=delimiter, nrows=100)
    except Exception as error:
        shutil.rmtree(dataset_dir, ignore_errors=True)
        raise ValueError(f"Ошибка чтения структуры файла: {error}")

    # Вычисляем колонки и типы один раз при сохранении
    fields = [str(col) for col in df_sample.columns]
    field_types = {
        str(field): _infer_field_type(df_sample[field])
        for field in df_sample.columns
    }

    # Паспорт схемы датасета
    meta = {
        "datasetId": dataset_id,
        "userId": user_id,
        "name": file_name,
        "format": file_format,
        "delimiter": delimiter,
        "sheetName": sheet_name,
        "fields": fields,
        "fieldTypes": field_types,
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
    meta = get_dataset_meta(user_id, dataset_id)
    if meta:
        file_name = meta.get("name") or meta.get("storedName")
        if file_name:
            path = _data_file(user_id, dataset_id, file_name)
            if path.exists():
                return path

    fallback_csv = _data_file(user_id, dataset_id, "data.csv")
    if fallback_csv.exists():
        return fallback_csv

    return None


def get_dataset_preview(
        user_id: str,
        dataset_id: str,
        limit: int = 500,
) -> dict | None:

    path = get_dataset_path(user_id, dataset_id)
    if not path:
        return None

    meta = get_dataset_meta(user_id, dataset_id) or {}
    file_format = meta.get("format")

    safe_limit = min(limit, 1000)
    try:
        if file_format == "excel":
            sheet_name = meta.get("sheetName")
            with pd.ExcelFile(path) as excel_file:
                target_sheet = sheet_name if sheet_name in excel_file.sheet_names else 0
                dataframe = pd.read_excel(excel_file, sheet_name=target_sheet, nrows=safe_limit)
        else:
            delimiter = meta.get("delimiter")
            if delimiter:
                dataframe = pd.read_csv(path, sep=delimiter, nrows=safe_limit)
            else:
                dataframe = pd.read_csv(path, nrows=safe_limit)
    except Exception as error:
        raise ValueError(f"Не удалось прочитать датасет: {error}")

    # Колонки и типы берем из meta.json
    fields = meta.get("fields") or [str(col) for col in dataframe.columns]
    field_types = meta.get("fieldTypes") or {
        str(field): _infer_field_type(dataframe[field])
        for field in dataframe.columns
    }
    return {
        "datasetId": dataset_id,
        "fields": fields,
        "fieldTypes": field_types,
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


def inspect_excel_sheets(file: UploadFile) -> list[str]:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in [".xlsx", ".xls"]:
        raise ValueError("Файл не является книгой Excel (.xlsx, .xls)")
    try:
        excel = pd.ExcelFile(file.file)
        sheets = excel.sheet_names
        file.file.seek(0)  # Сбрасываем указатель файла в начало
        return sheets
    except Exception as error:
        raise ValueError(f"Не удалось прочитать структуру Excel: {error}")
