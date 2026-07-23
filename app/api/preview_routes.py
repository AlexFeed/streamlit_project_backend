# app/api/preview_routes.py

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

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
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.put("/{session_id}")
def update_preview(
        session_id: str,
        payload: dict,
        current_user: Annotated[
            auth_service.User,
            Depends(auth_service.get_current_active_user),
        ],
):
    try:
        return preview_service.update_preview(
            session_id=session_id,
            user_id=current_user.id,
            schema=payload.get("schema"),
            dataset_id=payload.get("datasetId"),
        )
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=str(error))
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/{session_id}")
def get_preview(session_id: str):
    try:
        return preview_service.get_preview(session_id)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))


@router.delete("/{session_id}")
def delete_preview(
        session_id: str,
        current_user: Annotated[
            auth_service.User,
            Depends(auth_service.get_current_active_user),
        ],
):
    try:
        return preview_service.delete_preview(session_id, current_user.id)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail=str(error))
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error))
