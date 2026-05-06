from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.services import auth_service, dataset_service

router = APIRouter(prefix="/datasets")

# CRUD ЗАПРОСЫ ДЛЯ ВЗАИМОДЕЙСТВИЯ С ДАТАСЕТАМИ
@router.post("/upload")
async def upload_dataset(
        current_user: Annotated[auth_service.User, Depends(auth_service.get_current_active_user)],
        dataset: UploadFile = File(...),
):
    return dataset_service.save_dataset(current_user.id, dataset)


@router.get("/{dataset_id}")
async def get_dataset(
        dataset_id: str,
        current_user: Annotated[
            auth_service.User,
            Depends(auth_service.get_current_active_user),
        ],
):
    meta = dataset_service.get_dataset_meta(current_user.id, dataset_id)

    if not meta:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return meta


@router.delete("/{dataset_id}")
async def delete_dataset(
        dataset_id: str,
        current_user: Annotated[
            auth_service.User,
            Depends(auth_service.get_current_active_user),
        ],
):
    deleted = dataset_service.delete_dataset(current_user.id, dataset_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return {"deleted": True}