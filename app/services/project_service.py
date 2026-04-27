import json
import uuid
from datetime import datetime
from pathlib import Path

PROJECTS_DIR = Path("storage/projects")

# Backend часть управления проектами с главной страницы
def _now() -> str:
    return datetime.now().isoformat()


def _project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def _project_file(project_id: str) -> Path:
    return _project_dir(project_id) / "project.json"


def create_project(payload: dict) -> dict:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    project_id = str(uuid.uuid4())
    now = _now()

    project = {
        "id": project_id,
        "title": payload.get("title") or "Untitled dashboard",
        "description": payload.get("description") or "",
        "datasetMeta": payload.get("datasetMeta"),
        "editorState": payload.get("editorState") or {
            "components": []
        },
        "schema": payload.get("schema"),
        "createdAt": now,
        "updatedAt": now,
    }

    _project_dir(project_id).mkdir(parents=True, exist_ok=True)

    with _project_file(project_id).open("w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)

    return project


def get_project(project_id: str) -> dict | None:
    path = _project_file(project_id)

    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def update_project(project_id: str, payload: dict) -> dict | None:
    project = get_project(project_id)

    if not project:
        return None

    if "title" in payload:
        project["title"] = payload["title"] or "Untitled dashboard"

    if "description" in payload:
        project["description"] = payload["description"] or ""

    if "datasetMeta" in payload:
        project["datasetMeta"] = payload["datasetMeta"]

    if "editorState" in payload:
        project["editorState"] = payload["editorState"] or {"components": []}

    if "schema" in payload:
        project["schema"] = payload["schema"]

    project["updatedAt"] = _now()

    with _project_file(project_id).open("w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)

    return project


def list_projects() -> list[dict]:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    projects = []

    for project_dir in PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue

        path = project_dir / "project.json"

        if not path.exists():
            continue

        with path.open("r", encoding="utf-8") as f:
            project = json.load(f)

        projects.append({
            "id": project.get("id"),
            "title": project.get("title", "Untitled dashboard"),
            "description": project.get("description", ""),
            "datasetName": (project.get("datasetMeta") or {}).get("name"),
            "createdAt": project.get("createdAt"),
            "updatedAt": project.get("updatedAt"),
        })

    return sorted(projects, key=lambda p: p.get("updatedAt") or "", reverse=True)


def delete_project(project_id: str) -> bool:
    project_dir = _project_dir(project_id)

    if not project_dir.exists():
        return False

    for item in project_dir.iterdir():
        item.unlink()

    project_dir.rmdir()
    return True