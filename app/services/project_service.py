import json
import uuid
from datetime import datetime
import shutil
from pathlib import Path

from app.schemas.dashboard import validate_dashboard_schema
from app.services import dataset_service

PROJECTS_DIR = Path("storage/projects")

def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _project_dir(user_id: str, project_id: str) -> Path:
    return PROJECTS_DIR / user_id / project_id


def _project_file(user_id: str, project_id: str) -> Path:
    return _project_dir(user_id, project_id) / "project.json"


def create_project(user_id: str, payload: dict) -> dict:
    project_id = str(uuid.uuid4())
    now = _now()

    schema = payload.get("schema")
    if schema:
        schema = validate_dashboard_schema(schema)

    project = {
        "id": project_id,
        "userId": user_id,
        "title": payload.get("title") or "Untitled dashboard",
        "description": payload.get("description") or "",
        "datasets": payload.get("datasets") or [],
        "editorState": payload.get("editorState") or {"components": []},
        "schema": schema,
        "createdAt": now,
        "updatedAt": now,
    }

    _project_dir(user_id, project_id).mkdir(parents=True, exist_ok=True)

    with _project_file(user_id, project_id).open("w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)

    return project


def get_project(user_id: str, project_id: str) -> dict | None:
    path = _project_file(user_id, project_id)

    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def update_project(user_id: str, project_id: str, payload: dict) -> dict | None:
    project = get_project(user_id, project_id)

    if not project:
        return None

    if "title" in payload:
        project["title"] = payload["title"] or "Untitled dashboard"

    if "description" in payload:
        project["description"] = payload["description"] or ""

    if "datasets" in payload:
        old_ids = {
            ds.get("datasetId")
            for ds in (project.get("datasets") or [])
            if ds.get("datasetId")
        }
        new_datasets = payload["datasets"] or []
        new_ids = {
            ds.get("datasetId")
            for ds in new_datasets
            if ds.get("datasetId")
        }

        for removed_id in old_ids - new_ids:
            dataset_service.delete_dataset(user_id, removed_id)

        project["datasets"] = new_datasets

    if "editorState" in payload:
        project["editorState"] = payload["editorState"] or {"components": []}

    if "schema" in payload:
        schema = payload["schema"]
        project["schema"] = (
            validate_dashboard_schema(schema)
            if schema
            else None
        )

    project["updatedAt"] = _now()

    with _project_file(user_id, project_id).open("w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)

    return project


def list_projects(user_id: str) -> list[dict]:
    user_dir = PROJECTS_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    projects = []

    for project_dir in user_dir.iterdir():
        if not project_dir.is_dir():
            continue

        path = project_dir / "project.json"

        if not path.exists():
            continue

        with path.open("r", encoding="utf-8") as f:
            project = json.load(f)

        datasets = project.get("datasets") or []
        dataset_names = ", ".join(
            ds.get("name") for ds in datasets if ds.get("name")
        ) or None

        projects.append({
            "id": project.get("id"),
            "title": project.get("title", "Untitled dashboard"),
            "description": project.get("description", ""),
            "datasetName": dataset_names,
            "createdAt": project.get("createdAt"),
            "updatedAt": project.get("updatedAt"),
        })

    return sorted(
        projects,
        key=lambda project: project.get("updatedAt") or "",
        reverse=True,
    )


def delete_project(user_id: str, project_id: str) -> bool:
    project_dir = _project_dir(user_id, project_id)

    if not project_dir.exists():
        return False

    shutil.rmtree(project_dir)
    return True
