# app/api/preview_routes.py

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.services import auth_service
from app.services.preview_service import preview_service

router = APIRouter(prefix="/preview")


@router.post("")
def create_preview(
        payload: dict,
        current_user: Annotated[
            auth_service.User,
            Depends(auth_service.get_current_active_user),
        ],
):
    try:
        return preview_service.create_preview(
            user_id=current_user.id,
            schema=payload.get("schema"),
            dataset_id=payload.get("datasetId"),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/{session_id}")
def get_preview(session_id: str):
    try:
        return preview_service.get_preview(session_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))