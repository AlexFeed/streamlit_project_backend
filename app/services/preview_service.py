import uuid
from typing import Dict, Any

from app.services.dataset_service import get_dataset_path


class PreviewService:
    def __init__(self):
        # in-memory storage (для MVP)
        self._sessions: Dict[str, Dict[str, Any]] = {}

    def create_preview(self, user_id: str, schema: dict, dataset_id: str) -> dict:
        dataset_path = get_dataset_path(user_id, dataset_id)

        if not dataset_path:
            raise ValueError("Dataset not found")

        session_id = str(uuid.uuid4())

        self._sessions[session_id] = {
            "schema": schema,
            "datasetPath": str(dataset_path),
        }

        return {
            "sessionId": session_id,
            "previewUrl": f"http://localhost:8501/?session_id={session_id}",
        }

    def get_preview(self, session_id: str) -> dict:
        session = self._sessions.get(session_id)

        if not session:
            raise ValueError("Preview not found")

        return session


# singleton для MVP
preview_service = PreviewService()