from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse


import io
import zipfile

# Services
from app.services.generator_service import generate_streamlit_code
from app.services.preview_service import preview_service
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
        # Возвращает мета данные датасета
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



# ПРЕВЬЮ ДАШБОРДА
@router.post("/preview")
async def create_preview(payload: dict):
    try:
        result = preview_service.create_preview(
            schema=payload.get("schema"),
            dataset_id=payload.get("datasetId"),
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/preview/{session_id}")
async def get_preview(session_id: str):
    try:
        return preview_service.get_preview(session_id)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))



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