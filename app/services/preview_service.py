import os
import time
import uuid
from datetime import UTC, datetime
from threading import RLock
from typing import Any
from urllib.parse import urlencode

from app.schemas.dashboard import validate_dashboard_schema
from app.services.dataset_service import get_dataset_path


class PreviewService:
    def __init__(
        self,
        ttl_seconds: int | None = None,
        public_url: str | None = None,
    ):
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = RLock()
        self._ttl_seconds = ttl_seconds or int(
            os.getenv("PREVIEW_SESSION_TTL_SECONDS", "1800")
        )
        self._public_url = (
            public_url
            or os.getenv("PREVIEW_PUBLIC_URL", "http://localhost:8501")
        ).rstrip("/")

    def create_preview(self, user_id: str, schema: dict, dataset_id: str) -> dict:
        validated_schema = validate_dashboard_schema(schema)
        dataset_path = self._get_dataset_path_or_raise(user_id, dataset_id)
        session_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        with self._lock:
            self._cleanup_expired()
            self._sessions[session_id] = {
                "userId": user_id,
                "schema": validated_schema,
                "datasetId": dataset_id,
                "datasetPath": str(dataset_path.resolve()),
                "createdAt": now,
                "updatedAt": now,
                "revision": 1,
                "expiresAtMonotonic": time.monotonic() + self._ttl_seconds,
            }

        return self._build_client_response(session_id)

    def update_preview(
        self,
        session_id: str,
        user_id: str,
        schema: dict,
        dataset_id: str | None = None,
    ) -> dict:
        validated_schema = validate_dashboard_schema(schema)

        with self._lock:
            self._cleanup_expired()
            session = self._get_owned_session(session_id, user_id)
            next_dataset_id = dataset_id or session["datasetId"]
            dataset_path = self._get_dataset_path_or_raise(
                user_id,
                next_dataset_id,
            )

            session.update({
                "schema": validated_schema,
                "datasetId": next_dataset_id,
                "datasetPath": str(dataset_path.resolve()),
                "updatedAt": datetime.now(UTC).isoformat(),
                "revision": session["revision"] + 1,
                "expiresAtMonotonic": time.monotonic() + self._ttl_seconds,
            })

        return self._build_client_response(session_id)

    def get_preview(self, session_id: str) -> dict:
        with self._lock:
            self._cleanup_expired()
            session = self._sessions.get(session_id)

            if not session:
                raise ValueError("Preview not found or expired")

            session["expiresAtMonotonic"] = time.monotonic() + self._ttl_seconds

            return {
                "schema": session["schema"],
                "datasetPath": session["datasetPath"],
                "revision": session["revision"],
                "updatedAt": session["updatedAt"],
            }

    def delete_preview(self, session_id: str, user_id: str) -> dict:
        with self._lock:
            self._cleanup_expired()
            self._get_owned_session(session_id, user_id)
            del self._sessions[session_id]

        return {"deleted": True}

    def _get_owned_session(self, session_id: str, user_id: str) -> dict:
        session = self._sessions.get(session_id)

        if not session:
            raise ValueError("Preview not found or expired")
        if session["userId"] != user_id:
            raise PermissionError("Preview belongs to another user")

        return session

    def _get_dataset_path_or_raise(self, user_id: str, dataset_id: str):
        if not dataset_id:
            raise ValueError("datasetId is required")

        dataset_path = get_dataset_path(user_id, dataset_id)
        if not dataset_path:
            raise ValueError("Dataset not found")

        return dataset_path

    def _cleanup_expired(self) -> None:
        now = time.monotonic()
        expired_ids = [
            session_id
            for session_id, session in self._sessions.items()
            if session["expiresAtMonotonic"] <= now
        ]

        for session_id in expired_ids:
            del self._sessions[session_id]

    def _build_client_response(self, session_id: str) -> dict:
        session = self._sessions[session_id]
        query = urlencode({
            "session_id": session_id,
            "revision": session["revision"],
        })

        return {
            "sessionId": session_id,
            "previewUrl": f"{self._public_url}/?{query}",
            "revision": session["revision"],
            "expiresIn": self._ttl_seconds,
        }


preview_service = PreviewService()
