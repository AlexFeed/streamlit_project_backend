import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import preview_routes
from app.services import auth_service, dataset_service
from app.services.preview_runtime_service import PreviewRuntimeService
from app.services.preview_service import PreviewNotFoundError, PreviewService


def make_preview_schema(
    title: str = "Sales dashboard",
    data_sources: list[dict] | None = None,
) -> dict:
    sources = (
        [
            {
                "type": "backend_dataset",
                "datasetId": "dataset-1",
                "name": "sales.csv",
                "fields": ["date", "region", "sales"],
            }
        ]
        if data_sources is None
        else data_sources
    )
    return {
        "version": 2,
        "dashboard": {
            "title": title,
            "grid": {"columns": 12},
        },
        "dataSources": sources,
        "filters": [],
        "views": [
            {
                "id": "metric-1",
                "type": "metric",
                "datasetId": "dataset-1",
                "order": 1,
                "layout": {"width": 4, "height": 160},
                "title": "Total",
                "field": "sales",
                "aggregation": "sum",
            }
        ],
    }


# --- HTTP API routes (/preview) ---


class PreviewRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.datasets_dir = Path(self.temp_dir.name)
        self.service = PreviewService(
            ttl_seconds=60,
            public_url="http://preview.test/",
        )

        self.datasets_patch = patch.object(
            dataset_service,
            "DATASETS_DIR",
            self.datasets_dir,
        )
        self.service_patch = patch.object(
            preview_routes,
            "preview_service",
            self.service,
        )
        self.datasets_patch.start()
        self.service_patch.start()
        self.addCleanup(self.service_patch.stop)
        self.addCleanup(self.datasets_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def _make_client(self, user_id: str | None = "user-1") -> TestClient:
        app = FastAPI()
        app.include_router(preview_routes.router)
        if user_id is not None:
            app.dependency_overrides[auth_service.get_current_active_user] = lambda: (
                auth_service.User(
                    id=user_id,
                    email=f"{user_id}@example.com",
                )
            )
        return TestClient(app)

    def _create_dataset(
        self,
        user_id: str,
        dataset_id: str = "dataset-1",
        content: str = "region,sales\nA,10\n",
    ) -> Path:
        data_dir = self.datasets_dir / user_id / dataset_id
        data_dir.mkdir(parents=True, exist_ok=True)
        file_path = data_dir / "data.csv"
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def test_full_preview_http_lifecycle(self):
        self._create_dataset("user-1", "dataset-1")
        owner_client = self._make_client("user-1")
        anon_client = self._make_client(user_id=None)

        created = owner_client.post("/preview", json={"schema": make_preview_schema()})
        self.assertEqual(created.status_code, 200)
        created_body = created.json()
        session_id = created_body["sessionId"]
        self.assertEqual(created_body["revision"], 1)
        self.assertEqual(created_body["expiresIn"], 60)
        self.assertTrue(created_body["previewUrl"].startswith("http://preview.test/?"))
        self.assertIn(f"session_id={session_id}", created_body["previewUrl"])
        self.assertIn("revision=1", created_body["previewUrl"])
        self.assertIn("embed=true", created_body["previewUrl"])

        # Preview runtime reads the session without bearer auth
        fetched = anon_client.get(f"/preview/{session_id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["revision"], 1)
        self.assertIn("dataset-1", fetched.json()["datasetsPaths"])

        updated = owner_client.put(
            f"/preview/{session_id}",
            json={"schema": make_preview_schema(title="Updated dashboard")},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["revision"], 2)
        self.assertIn("revision=2", updated.json()["previewUrl"])

        refetched = anon_client.get(f"/preview/{session_id}")
        self.assertEqual(
            refetched.json()["schema"]["dashboard"]["title"],
            "Updated dashboard",
        )

        deleted = owner_client.delete(f"/preview/{session_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json(), {"deleted": True})
        self.assertEqual(anon_client.get(f"/preview/{session_id}").status_code, 404)

    def test_create_and_update_validate_schema_and_data_sources(self):
        self._create_dataset("user-1", "dataset-1")
        self._create_dataset("user-2", "foreign-ds")
        client = self._make_client("user-1")

        session_id = client.post(
            "/preview",
            json={"schema": make_preview_schema()},
        ).json()["sessionId"]

        invalid_cases = [
            ("missing_schema", {}, 422),
            ("non_dict_schema", {"schema": "not-a-dict"}, 422),
            ("invalid_schema_v2", {"schema": {"version": 999}}, 422),
            (
                "empty_data_sources",
                {"schema": make_preview_schema(data_sources=[])},
                422,
            ),
            (
                "missing_dataset_id",
                {
                    "schema": make_preview_schema(
                        data_sources=[{"type": "backend_dataset", "name": "sales.csv"}]
                    )
                },
                400,
            ),
            (
                "missing_dataset_file",
                {
                    "schema": make_preview_schema(
                        data_sources=[
                            {
                                "type": "backend_dataset",
                                "datasetId": "does-not-exist",
                                "name": "sales.csv",
                            }
                        ]
                    )
                },
                400,
            ),
            (
                "foreign_user_dataset",
                {
                    "schema": make_preview_schema(
                        data_sources=[
                            {
                                "type": "backend_dataset",
                                "datasetId": "foreign-ds",
                                "name": "sales.csv",
                            }
                        ]
                    )
                },
                400,
            ),
        ]

        for label, payload, expected_status in invalid_cases:
            with self.subTest(endpoint="POST", case=label):
                self.assertEqual(
                    client.post("/preview", json=payload).status_code,
                    expected_status,
                )
            with self.subTest(endpoint="PUT", case=label):
                self.assertEqual(
                    client.put(f"/preview/{session_id}", json=payload).status_code,
                    expected_status,
                )

    def test_foreign_user_cannot_update_or_delete_preview_session(self):
        self._create_dataset("user-1", "dataset-1")
        self._create_dataset("user-2", "dataset-1")
        owner_client = self._make_client("user-1")
        other_client = self._make_client("user-2")

        session_id = owner_client.post(
            "/preview",
            json={"schema": make_preview_schema(title="Owner title")},
        ).json()["sessionId"]

        put_response = other_client.put(
            f"/preview/{session_id}",
            json={"schema": make_preview_schema(title="Hijacked")},
        )
        delete_response = other_client.delete(f"/preview/{session_id}")

        self.assertEqual(put_response.status_code, 403)
        self.assertEqual(delete_response.status_code, 403)

        session = owner_client.get(f"/preview/{session_id}").json()
        self.assertEqual(session["revision"], 1)
        self.assertEqual(session["schema"]["dashboard"]["title"], "Owner title")

    def test_missing_session_returns_404_across_get_put_and_delete(self):
        client = self._make_client("user-1")

        self.assertEqual(client.get("/preview/missing-id").status_code, 404)
        self.assertEqual(
            client.put(
                "/preview/missing-id",
                json={"schema": make_preview_schema()},
            ).status_code,
            404,
        )
        self.assertEqual(client.delete("/preview/missing-id").status_code, 404)

    def test_mutation_routes_require_authentication(self):
        anon_client = self._make_client(user_id=None)

        self.assertEqual(
            anon_client.post(
                "/preview", json={"schema": make_preview_schema()}
            ).status_code,
            401,
        )
        self.assertEqual(
            anon_client.put(
                "/preview/any-id",
                json={"schema": make_preview_schema()},
            ).status_code,
            401,
        )
        self.assertEqual(anon_client.delete("/preview/any-id").status_code, 401)


# --- Session storage & TTL behavior (PreviewService) ---


class PreviewServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root_dir = Path(self.temp_dir.name)
        self.addCleanup(self.temp_dir.cleanup)

    def test_creates_preview_with_multiple_datasets(self):
        path_a = self.root_dir / "sales.csv"
        path_b = self.root_dir / "targets.csv"
        path_a.write_text("region,sales\nA,10\n", encoding="utf-8")
        path_b.write_text("region,target\nA,15\n", encoding="utf-8")

        schema = make_preview_schema(
            data_sources=[
                {"type": "backend_dataset", "datasetId": "ds-a", "name": "sales.csv"},
                {"type": "backend_dataset", "datasetId": "ds-b", "name": "targets.csv"},
            ]
        )
        service = PreviewService(ttl_seconds=60)

        def resolve_dataset_path(user_id: str, dataset_id: str) -> Path:
            return path_a if dataset_id == "ds-a" else path_b

        with patch(
            "app.services.preview_service.get_dataset_path",
            side_effect=resolve_dataset_path,
        ):
            created = service.create_preview("user-1", schema)
            session = service.get_preview(created["sessionId"])

            self.assertEqual(len(session["datasetsPaths"]), 2)
            self.assertEqual(session["datasetsPaths"]["ds-a"], str(path_a.resolve()))
            self.assertEqual(session["datasetsPaths"]["ds-b"], str(path_b.resolve()))

    def test_expired_session_is_cleaned_up_on_access(self):
        dataset_path = self.root_dir / "data.csv"
        dataset_path.write_text("region,sales\nA,10\n", encoding="utf-8")
        service = PreviewService(ttl_seconds=60)
        clock = [100.0]

        with (
            patch(
                "app.services.preview_service.get_dataset_path",
                return_value=dataset_path,
            ),
            patch(
                "app.services.preview_service.time.monotonic",
                side_effect=lambda: clock[0],
            ),
        ):
            session_id = service.create_preview("user-1", make_preview_schema())[
                "sessionId"
            ]

            clock[0] = 161.0
            with self.assertRaises(PreviewNotFoundError):
                service.get_preview(session_id)
            with self.assertRaises(PreviewNotFoundError):
                service.update_preview(session_id, "user-1", make_preview_schema())
            with self.assertRaises(PreviewNotFoundError):
                service.delete_preview(session_id, "user-1")

    def test_get_preview_extends_session_ttl(self):
        dataset_path = self.root_dir / "data.csv"
        dataset_path.write_text("region,sales\nA,10\n", encoding="utf-8")
        service = PreviewService(ttl_seconds=60)
        clock = [100.0]

        with (
            patch(
                "app.services.preview_service.get_dataset_path",
                return_value=dataset_path,
            ),
            patch(
                "app.services.preview_service.time.monotonic",
                side_effect=lambda: clock[0],
            ),
        ):
            session_id = service.create_preview("user-1", make_preview_schema())[
                "sessionId"
            ]

            # Reading at t=150 slides expiry to t=210
            clock[0] = 150.0
            self.assertEqual(service.get_preview(session_id)["revision"], 1)

            clock[0] = 200.0
            self.assertEqual(service.get_preview(session_id)["revision"], 1)

            clock[0] = 261.0
            with self.assertRaises(PreviewNotFoundError):
                service.get_preview(session_id)


# --- Streamlit preview subprocess lifecycle (PreviewRuntimeService) ---


class PreviewRuntimeServiceTests(unittest.TestCase):
    def test_start_is_idempotent_and_fails_when_script_missing(self):
        runtime = PreviewRuntimeService()
        fake_process = MagicMock()
        fake_process.poll.return_value = None

        with patch(
            "app.services.preview_runtime_service.subprocess.Popen",
            return_value=fake_process,
        ) as popen_mock:
            runtime.start()
            self.assertTrue(runtime.is_running())
            runtime.start()
            self.assertEqual(popen_mock.call_count, 1)

        missing_runtime = PreviewRuntimeService()
        missing_runtime.preview_app_path = Path("non_existent_preview_render.py")
        with self.assertRaises(FileNotFoundError):
            missing_runtime.start()

    def test_stop_terminates_process_and_kills_on_timeout(self):
        runtime = PreviewRuntimeService()
        graceful_process = MagicMock()
        graceful_process.poll.return_value = None
        runtime.process = graceful_process

        runtime.stop()
        graceful_process.terminate.assert_called_once()
        graceful_process.wait.assert_called_once_with(timeout=5)
        graceful_process.kill.assert_not_called()
        self.assertIsNone(runtime.process)

        stuck_process = MagicMock()
        stuck_process.poll.return_value = None
        stuck_process.wait.side_effect = [
            subprocess.TimeoutExpired(cmd="streamlit", timeout=5),
            0,
        ]
        runtime.process = stuck_process

        runtime.stop()
        stuck_process.terminate.assert_called_once()
        stuck_process.kill.assert_called_once()
        self.assertEqual(stuck_process.wait.call_count, 2)
        self.assertIsNone(runtime.process)


if __name__ == "__main__":
    unittest.main()
