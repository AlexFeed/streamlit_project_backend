from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse
from app.services.generator import generate_streamlit_code

import io
import zipfile

from app.services.dataset_service import (
    delete_dataset,
    get_dataset_meta,
    get_dataset_path,
    save_dataset,
)

router = APIRouter()

# CRUD ЗАПРОСЫ ДЛЯ ВЗАИМОДЕЙСТВИЯ С ДАТАСЕТАМИ
@router.post("/datasets/upload")
async def upload_dataset(dataset: UploadFile = File(...)):
    try:
        return save_dataset(dataset)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Dataset upload failed: {error}")


@router.get("/datasets/{dataset_id}")
async def get_dataset(dataset_id: str):
    meta = get_dataset_meta(dataset_id)

    if not meta:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return meta


@router.delete("/datasets/{dataset_id}")
async def remove_dataset(dataset_id: str):
    deleted = delete_dataset(dataset_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return {"deleted": True}


# ГЕНЕРАЦИЯ STREAMLIT КОДА
@router.post("/generate")
async def generate_dashboard(payload: dict):
    schema = payload.get("schema")
    dataset_id = payload.get("datasetId")

    if not schema:
        raise HTTPException(status_code=400, detail="Schema is required")

    if not dataset_id:
        raise HTTPException(status_code=400, detail="datasetId is required")

    dataset_path = get_dataset_path(dataset_id)
    dataset_meta = get_dataset_meta(dataset_id)

    if not dataset_path or not dataset_meta:
        raise HTTPException(status_code=404, detail="Dataset not found")

    code = generate_streamlit_code(schema)

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("app.py", code)
        zip_file.write(dataset_path, f"data/{dataset_meta['name']}")
        zip_file.writestr(
            "requirements.txt",
            "streamlit\npandas\n",
        )

    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=dashboard_project.zip"
        },
    )