import io
import zipfile
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.services import auth_service, dataset_service
from app.services.generator_service import generate_streamlit_code

router = APIRouter()

# ГЕНЕРАЦИЯ STREAMLIT КОДА
@router.post("/generate")
async def generate_dashboard(payload: dict, current_user: Annotated[
    auth_service.User,
    Depends(auth_service.get_current_active_user),
],):
    schema = payload.get("schema")
    dataset_id = payload.get("datasetId")

    if not schema:
        raise HTTPException(status_code=400, detail="Schema is required")

    if not dataset_id:
        raise HTTPException(status_code=400, detail="datasetId is required")

    dataset_path = dataset_service.get_dataset_path(
        current_user.id,
        dataset_id,
    )
    dataset_meta = dataset_service.get_dataset_meta(
        current_user.id,
        dataset_id,
    )

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