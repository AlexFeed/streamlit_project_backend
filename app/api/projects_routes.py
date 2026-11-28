from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.dashboard import DashboardSchema
from app.services import auth_service, project_service

router = APIRouter(prefix="/projects")


class ProjectPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    title: str | None = None
    description: str | None = None
    preview_image: str | None = Field(default=None, alias="previewImage")
    datasets: list[dict[str, Any]] | None = None
    editor_state: dict[str, Any] | None = Field(default=None, alias="editorState")
    dashboard_schema: DashboardSchema | None = Field(default=None, alias="schema")


# PROJECT MANAGEMENT
@router.get("")
def list_projects(current_user: Annotated[auth_service.User, Depends(auth_service.get_current_active_user)]):
    return project_service.list_projects(current_user.id)


@router.post("")
def create_project(
        payload: ProjectPayload,
        current_user: Annotated[auth_service.User, Depends(auth_service.get_current_active_user)],
):
    try:
        return project_service.create_project(
            current_user.id,
            payload.model_dump(by_alias=True, exclude_unset=True),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/{project_id}")
def get_project(
        project_id: str,
        current_user: Annotated[auth_service.User, Depends(auth_service.get_current_active_user)],
):
    project = project_service.get_project(current_user.id, project_id)

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


@router.put("/{project_id}")
def update_project(
        project_id: str,
        payload: ProjectPayload,
        current_user: Annotated[auth_service.User, Depends(auth_service.get_current_active_user)],
):
    try:
        project = project_service.update_project(
            current_user.id,
            project_id,
            payload.model_dump(by_alias=True, exclude_unset=True),
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    return project


@router.delete("/{project_id}")
def delete_project(
        project_id: str,
        current_user: Annotated[auth_service.User, Depends(auth_service.get_current_active_user)],
):
    deleted = project_service.delete_project(current_user.id, project_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Project not found")

    return {"deleted": True}
