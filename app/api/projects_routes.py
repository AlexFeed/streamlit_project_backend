from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from app.services import auth_service, project_service

router = APIRouter(prefix="/projects")

# УПРАВЛЕНИЕ ПРОЕКТАМИ
@router.get("")
def list_projects(current_user: Annotated[auth_service.User, Depends(auth_service.get_current_active_user)]):
    return project_service.list_projects(current_user.id)


@router.post("")
def create_project(
        payload: dict,
        current_user: Annotated[auth_service.User, Depends(auth_service.get_current_active_user)],
):
    return project_service.create_project(current_user.id, payload)


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
        payload: dict,
        current_user: Annotated[auth_service.User, Depends(auth_service.get_current_active_user)],
):
    project = project_service.update_project(
        current_user.id,
        project_id,
        payload,
    )

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