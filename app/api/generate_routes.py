from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.schemas.dashboard import DashboardSchemaPayload
from app.services import auth_service
from app.services.generator_service import DatasetNotFoundError, build_dashboard_zip

router = APIRouter()


# STREAMLIT CODE GENERATION
@router.post("/generate")
def generate_dashboard(
    payload: DashboardSchemaPayload,
    current_user: Annotated[
        auth_service.User,
        Depends(auth_service.get_current_active_user),
    ],
):
    try:
        buffer = build_dashboard_zip(
            current_user.id,
            payload.dashboard_schema.model_dump(by_alias=True),
        )
    except DatasetNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=dashboard_project.zip"},
    )
