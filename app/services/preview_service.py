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

    def create_preview(self, user_id: str, schema: dict) -> dict:
        validated_schema = validate_dashboard_schema(schema)
        datasets_paths = self._resolve_datasets_paths(user_id, validated_schema)
        session_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        with self._lock:
            self._cleanup_expired()
            self._sessions[session_id] = {
                "userId": user_id,
                "schema": validated_schema,
                "datasetsPaths": datasets_paths,
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
    ) -> dict:
        validated_schema = validate_dashboard_schema(schema)

        with self._lock:
            self._cleanup_expired()
            session = self._get_owned_session(session_id, user_id)
            datasets_paths = self._resolve_datasets_paths(user_id, validated_schema)

            session.update({
                "schema": validated_schema,
                "datasetsPaths": datasets_paths,
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
                "datasetsPaths": session["datasetsPaths"],
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

    def _get_dataset_path_or_raise(self, user_id: str, dataset_id: str) -> Path:
        if not dataset_id:
            raise ValueError("datasetId is required")

        dataset_path = get_dataset_path(user_id, dataset_id)
        if not dataset_path:
            raise ValueError(f"Dataset '{dataset_id}' not found")

        return dataset_path

    def _resolve_datasets_paths(
        self,
        user_id: str,
        validated_schema: dict,
    ) -> dict[str, str]:
        data_sources = validated_schema.get("dataSources") or []
        if not data_sources:
            raise ValueError("dataSources are required")

        datasets_paths: dict[str, str] = {}
        for ds in data_sources:
            ds_id = ds.get("datasetId")
            if not ds_id:
                raise ValueError("datasetId is required for each dataSource")
            path = self._get_dataset_path_or_raise(user_id, ds_id)
            datasets_paths[ds_id] = str(path.resolve())

        return datasets_paths

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
