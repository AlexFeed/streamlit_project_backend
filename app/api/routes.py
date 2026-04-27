from fastapi import APIRouter, File, HTTPException, UploadFile, Depends
from fastapi.responses import PlainTextResponse, StreamingResponse

import io
import zipfile

# Services
from app.services.generator_service import generate_streamlit_code
from app.services.preview_service import preview_service
from app.services import project_service, dataset_service
from app.services.dataset_service import (
    delete_dataset,
    get_dataset_meta,
    get_dataset_path,
    save_dataset,
)
from app.services import auth_service
from app.api.auth_dependencies import get_current_user

router = APIRouter()


# УПРАВЛЕНИЕ LOGIN
@router.post("/auth/register")
def register(payload: dict):
    try:
        return auth_service.register_user(
            email=payload.get("email", ""),
            password=payload.get("password", ""),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/auth/login")
def login(payload: dict):
    try:
        return auth_service.login_user(
            email=payload.get("email", ""),
            password=payload.get("password", ""),
        )
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error))


@router.get("/auth/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user


# УПРАВЛЕНИЕ ПРОЕКТАМИ
@router.get("/projects")
def list_projects(current_user: dict = Depends(get_current_user)):
    return project_service.list_projects(current_user["id"])


@router.post("/projects")
def create_project(
        payload: dict,
        current_user: dict = Depends(get_current_user),
):
    return project_service.create_project(current_user["id"], payload)


@router.get("/projects/{project_id}")
def get_project(
        project_id: str,
        current_user: dict = Depends(get_current_user),
):
    project = project_service.get_project(current_user["id"], project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


@router.put("/projects/{project_id}")
def update_project(
        project_id: str,
        payload: dict,
        current_user: dict = Depends(get_current_user),
):
    project = project_service.update_project(
        current_user["id"],
        project_id,
        payload,
    )

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


@router.delete("/projects/{project_id}")
def delete_project(
        project_id: str,
        current_user: dict = Depends(get_current_user),
):
    deleted = project_service.delete_project(current_user["id"], project_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")

    return {"deleted": True}


# CRUD ЗАПРОСЫ ДЛЯ ВЗАИМОДЕЙСТВИЯ С ДАТАСЕТАМИ
@router.post("/datasets/upload")
async def upload_dataset(
        dataset: UploadFile = File(...),
        current_user: dict = Depends(get_current_user),
):
    return dataset_service.save_dataset(current_user["id"], dataset)


@router.get("/datasets/{dataset_id}")
async def get_dataset(
        dataset_id: str,
        current_user: dict = Depends(get_current_user),
):
    meta = dataset_service.get_dataset_meta(current_user["id"], dataset_id)

    if not meta:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return meta


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(
        dataset_id: str,
        current_user: dict = Depends(get_current_user),
):
    deleted = dataset_service.delete_dataset(current_user["id"], dataset_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return {"deleted": True}


# ПРЕВЬЮ ДАШБОРДА
@router.post("/preview")
async def create_preview(
        payload: dict,
        current_user: dict = Depends(get_current_user),
):
    try:
        return preview_service.create_preview(
            current_user["id"],
            payload.get("schema"),
            payload.get("datasetId"),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/preview/{session_id}")
async def get_preview(session_id: str):
    try:
        return preview_service.get_preview(session_id)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ГЕНЕРАЦИЯ STREAMLIT КОДА
@router.post("/generate")
async def generate_dashboard(payload: dict, current_user: dict = Depends(get_current_user)):
    schema = payload.get("schema")
    dataset_id = payload.get("datasetId")

    if not schema:
        raise HTTPException(status_code=400, detail="Schema is required")

    if not dataset_id:
        raise HTTPException(status_code=400, detail="datasetId is required")

    dataset_path = dataset_service.get_dataset_path(
        current_user["id"],
        dataset_id,
    )
    dataset_meta = get_dataset_meta(
        current_user["id"],
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
