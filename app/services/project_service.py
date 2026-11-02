import base64
import binascii
import json
import uuid
from datetime import datetime, UTC
import shutil
from pathlib import Path

from app.schemas.dashboard import validate_dashboard_schema
from app.services import dataset_service

PROJECTS_DIR = Path("storage/projects")
MAX_PREVIEW_IMAGE_BYTES = 4 * 1024 * 1024
PREVIEW_IMAGE_TYPES = {
    "image/jpeg": b"\xff\xd8\xff",
    "image/png": b"\x89PNG\r\n\x1a\n",
}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _project_dir(user_id: str, project_id: str) -> Path:
    return PROJECTS_DIR / user_id / project_id


def _project_file(user_id: str, project_id: str) -> Path:
    return _project_dir(user_id, project_id) / "project.json"


def _validate_preview_image(value: object) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str) or len(value) > MAX_PREVIEW_IMAGE_BYTES * 2:
        raise ValueError("Preview image is invalid or too large")

    try:
        header, encoded_image = value.split(",", maxsplit=1)
        media_type = header.removeprefix("data:").removesuffix(";base64")
        expected_signature = PREVIEW_IMAGE_TYPES.get(media_type)
        if expected_signature is None:
            raise ValueError("Preview image must be a JPEG or PNG data URL")

        image_bytes = base64.b64decode(encoded_image, validate=True)
    except (ValueError, binascii.Error) as error:
        raise ValueError("Preview image is not a valid base64 data URL") from error

    if (
        len(image_bytes) > MAX_PREVIEW_IMAGE_BYTES
        or not image_bytes.startswith(expected_signature)
    ):
        raise ValueError("Preview image is invalid or too large")

    return value


def _project_preview_image(project: dict) -> str | None:
    editor_state = project.get("editorState")
    nested_preview = (
        editor_state.get("previewImage")
        if isinstance(editor_state, dict)
        else None
    )
    return project.get("previewImage") or nested_preview


def create_project(user_id: str, payload: dict) -> dict:
    project_id = str(uuid.uuid4())
    now = _now()

    schema = payload.get("schema")
    if schema:
        schema = validate_dashboard_schema(schema)

    editor_state = payload.get("editorState") or {"components": []}
    preview_image = _validate_preview_image(
        payload.get("previewImage")
        if "previewImage" in payload
        else (
            editor_state.get("previewImage")
            if isinstance(editor_state, dict)
            else None
        )
    )
    if preview_image and isinstance(editor_state, dict):
        editor_state = {**editor_state, "previewImage": preview_image}

    project = {
        "id": project_id,
        "userId": user_id,
        "title": payload.get("title") or "Untitled dashboard",
        "description": payload.get("description") or "",
        "previewImage": preview_image,
        "datasets": payload.get("datasets") or [],
        "editorState": editor_state,
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
        project["datasets"] = payload["datasets"] or []

    if "editorState" in payload:
        project["editorState"] = payload["editorState"] or {"components": []}

    if "previewImage" in payload:
        preview_image = _validate_preview_image(payload["previewImage"])
    elif (
        "editorState" in payload
        and isinstance(project["editorState"], dict)
        and "previewImage" in project["editorState"]
    ):
        preview_image = _validate_preview_image(
            project["editorState"]["previewImage"]
        )
    else:
        preview_image = _project_preview_image(project)

    project["previewImage"] = preview_image
    if isinstance(project["editorState"], dict):
        editor_state = dict(project["editorState"])
        if preview_image:
            editor_state["previewImage"] = preview_image
        else:
            editor_state.pop("previewImage", None)
        project["editorState"] = editor_state

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
            "previewImage": _project_preview_image(project),
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
