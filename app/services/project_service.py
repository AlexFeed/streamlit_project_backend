import json
import uuid
from datetime import datetime
import shutil
from pathlib import Path

PROJECTS_DIR = Path("storage/projects")

# Backend С‡Р°СЃС‚СЊ СѓРїСЂР°РІР»РµРЅРёСЏ РїСЂРѕРµРєС‚Р°РјРё СЃ РіР»Р°РІРЅРѕР№ СЃС‚СЂР°РЅРёС†С‹
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

    project = {
        "id": project_id,
        "userId": user_id,
        "title": payload.get("title") or "Untitled dashboard",
        "description": payload.get("description") or "",
        "datasetMeta": payload.get("datasetMeta"),
        "editorState": payload.get("editorState") or {"components": []},
        "schema": payload.get("schema"),
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

    if "datasetMeta" in payload:
        project["datasetMeta"] = payload["datasetMeta"]

    if "editorState" in payload:
        project["editorState"] = payload["editorState"] or {"components": []}

    if "schema" in payload:
        project["schema"] = payload["schema"]

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

        projects.append({
            "id": project.get("id"),
            "title": project.get("title", "Untitled dashboard"),
            "description": project.get("description", ""),
            "datasetName": (project.get("datasetMeta") or {}).get("name"),
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
