import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.projects_routes import router as projects_router
from app.services import auth_service, project_service

JPEG_PREVIEW = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xdb").decode(
    "ascii"
)
PNG_PREVIEW = "data:image/png;base64," + base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00"
).decode("ascii")


def make_valid_schema(title: str = "Sales dashboard") -> dict:
    return {
        "version": 2,
        "dashboard": {"title": title, "grid": {"columns": 12}},
        "dataSources": [
            {
                "type": "backend_dataset",
                "datasetId": "dataset-1",
                "name": "sales.csv",
                "fields": ["region", "sales"],
            }
        ],
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


# --- HTTP API routes (/projects) ---


class ProjectRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.projects_dir = Path(self.temp_dir.name) / "projects"
        self.projects_patch = patch.object(
            project_service,
            "PROJECTS_DIR",
            self.projects_dir,
        )
        self.projects_patch.start()
        self.addCleanup(self.projects_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def _make_client(self, user_id: str | None = "user-1") -> TestClient:
        app = FastAPI()
        app.include_router(projects_router)
        if user_id is not None:
            app.dependency_overrides[auth_service.get_current_active_user] = lambda: (
                auth_service.User(
                    id=user_id,
                    email=f"{user_id}@example.com",
                )
            )
        return TestClient(app)

    # --- Creation (POST /projects) ---

    def test_create_project_applies_defaults_and_validates_full_payload(self):
        client = self._make_client("user-1")

        minimal = client.post("/projects", json={})
        self.assertEqual(minimal.status_code, 200)
        minimal_body = minimal.json()
        self.assertEqual(minimal_body["userId"], "user-1")
        self.assertEqual(minimal_body["title"], "Untitled dashboard")
        self.assertEqual(minimal_body["description"], "")
        self.assertEqual(minimal_body["datasets"], [])
        self.assertEqual(minimal_body["editorState"], {"components": []})
        self.assertIsNone(minimal_body["schema"])
        self.assertIsNone(minimal_body["previewImage"])

        full = client.post(
            "/projects",
            json={
                "title": "Q1 Sales",
                "description": "Quarterly overview",
                "datasets": [{"datasetId": "dataset-1", "name": "sales.csv"}],
                "previewImage": PNG_PREVIEW,
                "schema": make_valid_schema("Q1 Sales"),
            },
        )
        self.assertEqual(full.status_code, 200)
        full_body = full.json()
        self.assertEqual(full_body["title"], "Q1 Sales")
        self.assertEqual(full_body["previewImage"], PNG_PREVIEW)
        self.assertEqual(full_body["schema"]["dashboard"]["title"], "Q1 Sales")

    def test_create_rejects_invalid_schema_and_invalid_preview_images(self):
        client = self._make_client("user-1")
        oversized_png = "data:image/png;base64," + base64.b64encode(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * project_service.MAX_PREVIEW_IMAGE_BYTES
        ).decode("ascii")
        mismatched_magic = "data:image/png;base64," + base64.b64encode(
            b"\xff\xd8\xff\xdb"
        ).decode("ascii")
        missing_data_prefix = "image/jpeg," + base64.b64encode(
            b"\xff\xd8\xff\xdb"
        ).decode("ascii")

        cases = [
            ("invalid_schema", {"schema": {"version": 999}}),
            ("svg_mime", {"previewImage": "data:image/svg+xml;base64,PHN2Zz4="}),
            ("broken_base64", {"previewImage": "data:image/jpeg;base64,!!!not-b64!!!"}),
            ("mismatched_magic_bytes", {"previewImage": mismatched_magic}),
            ("missing_data_prefix", {"previewImage": missing_data_prefix}),
            ("oversized_image", {"previewImage": oversized_png}),
        ]

        for label, payload in cases:
            with self.subTest(case=label):
                response = client.post("/projects", json=payload)
                self.assertEqual(response.status_code, 422)

    # --- Listing (GET /projects) ---

    def test_list_projects_isolates_users_sorts_by_updated_at_and_formats_datasets(
        self,
    ):
        client_a = self._make_client("user-1")
        client_b = self._make_client("user-2")

        with patch(
            "app.services.project_service._now",
            side_effect=[
                "2026-01-01T10:00:00+00:00",
                "2026-01-02T10:00:00+00:00",
                "2026-01-03T10:00:00+00:00",
            ],
        ):
            older = client_a.post(
                "/projects",
                json={
                    "title": "Older",
                    "datasets": [{"name": "a.csv"}, {"name": "b.csv"}],
                },
            ).json()
            newer = client_a.post("/projects", json={"title": "Newer"}).json()
            client_b.post("/projects", json={"title": "Other user project"})

        # Stray files and empty directories in user-1 folder must be ignored safely
        (self.projects_dir / "user-1" / "empty-dir").mkdir()
        (self.projects_dir / "user-1" / "notes.txt").write_text("hi", encoding="utf-8")

        response = client_a.get("/projects")
        self.assertEqual(response.status_code, 200)
        items = response.json()
        self.assertEqual([item["id"] for item in items], [newer["id"], older["id"]])
        self.assertIsNone(items[0]["datasetName"])
        self.assertEqual(items[1]["datasetName"], "a.csv, b.csv")

    # --- Read & update (GET/PUT /projects/{project_id}) ---

    def test_get_and_update_project_handles_partial_fields_clearing_and_errors(self):
        owner_client = self._make_client("user-1")
        other_client = self._make_client("user-2")

        created = owner_client.post(
            "/projects",
            json={
                "title": "Initial",
                "description": "v1",
                "previewImage": JPEG_PREVIEW,
                "schema": make_valid_schema("Initial"),
            },
        ).json()
        project_id = created["id"]

        self.assertEqual(owner_client.get(f"/projects/{project_id}").status_code, 200)
        self.assertEqual(other_client.get(f"/projects/{project_id}").status_code, 404)
        self.assertEqual(owner_client.get("/projects/missing-id").status_code, 404)

        # Invalid update must return 422 without corrupting the stored project
        bad_update = owner_client.put(
            f"/projects/{project_id}",
            json={"schema": {"version": 999}},
        )
        self.assertEqual(bad_update.status_code, 422)
        self.assertEqual(
            owner_client.get(f"/projects/{project_id}").json()["title"],
            "Initial",
        )

        # Partial update omitting schema/previewImage must preserve them
        renamed = owner_client.put(
            f"/projects/{project_id}",
            json={"title": "Renamed"},
        )
        self.assertEqual(renamed.status_code, 200)
        renamed_body = renamed.json()
        self.assertEqual(renamed_body["title"], "Renamed")
        self.assertEqual(renamed_body["previewImage"], JPEG_PREVIEW)
        self.assertEqual(renamed_body["schema"]["dashboard"]["title"], "Initial")

        # Valid partial update clears previewImage & schema explicitly
        cleared = owner_client.put(
            f"/projects/{project_id}",
            json={
                "title": "Updated",
                "description": "v2",
                "datasets": [{"name": "sales.csv"}],
                "previewImage": "",
                "schema": None,
            },
        )
        self.assertEqual(cleared.status_code, 200)
        cleared_body = cleared.json()
        self.assertEqual(cleared_body["title"], "Updated")
        self.assertEqual(cleared_body["description"], "v2")
        self.assertEqual(cleared_body["datasets"], [{"name": "sales.csv"}])
        self.assertIsNone(cleared_body["previewImage"])
        self.assertNotIn("previewImage", cleared_body["editorState"])
        self.assertIsNone(cleared_body["schema"])

        # Foreign user and missing ID receive 404 on PUT
        self.assertEqual(
            other_client.put(
                f"/projects/{project_id}",
                json={"title": "Hijacked"},
            ).status_code,
            404,
        )
        self.assertEqual(
            owner_client.put("/projects/missing-id", json={"title": "X"}).status_code,
            404,
        )

    # --- Delete (DELETE /projects/{project_id}) ---

    def test_delete_removes_owner_project_and_blocks_other_user(self):
        owner_client = self._make_client("user-1")
        other_client = self._make_client("user-2")
        project_id = owner_client.post("/projects", json={"title": "Temp"}).json()["id"]
        project_dir = self.projects_dir / "user-1" / project_id
        self.assertTrue(project_dir.exists())

        self.assertEqual(
            other_client.delete(f"/projects/{project_id}").status_code,
            404,
        )
        self.assertTrue(project_dir.exists())

        deleted = owner_client.delete(f"/projects/{project_id}")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(deleted.json(), {"deleted": True})
        self.assertFalse(project_dir.exists())
        self.assertEqual(owner_client.get(f"/projects/{project_id}").status_code, 404)
        self.assertEqual(
            owner_client.delete(f"/projects/{project_id}").status_code,
            404,
        )

    # --- Authentication & path traversal protection ---

    def test_unauthenticated_requests_return_401(self):
        client = self._make_client(user_id=None)

        self.assertEqual(client.get("/projects").status_code, 401)
        self.assertEqual(client.post("/projects", json={}).status_code, 401)
        self.assertEqual(client.get("/projects/some-id").status_code, 401)
        self.assertEqual(client.put("/projects/some-id", json={}).status_code, 401)
        self.assertEqual(client.delete("/projects/some-id").status_code, 401)

    def test_path_traversal_project_id_is_rejected_without_touching_other_users(self):
        victim_client = self._make_client("user-2")
        attacker_client = self._make_client("user-1")
        victim_id = victim_client.post(
            "/projects",
            json={"title": "Victim project"},
        ).json()["id"]
        victim_dir = self.projects_dir / "user-2" / victim_id
        self.assertTrue(victim_dir.exists())

        self.assertEqual(
            attacker_client.get(f"/projects/..%2Fuser-2%2F{victim_id}").status_code,
            404,
        )
        self.assertEqual(
            attacker_client.put(
                f"/projects/..%2Fuser-2%2F{victim_id}",
                json={"title": "Pwned"},
            ).status_code,
            404,
        )
        self.assertEqual(
            attacker_client.delete("/projects/..%2Fuser-2").status_code,
            404,
        )
        self.assertIsNone(
            project_service.get_project("user-1", f"../user-2/{victim_id}")
        )
        self.assertIsNone(
            project_service.get_project("user-1", f"..\\user-2\\{victim_id}")
        )
        self.assertFalse(project_service.delete_project("user-1", "../user-2"))
        self.assertFalse(project_service.delete_project("user-1", "..\\user-2"))
        self.assertTrue(victim_dir.exists())


# --- Project card preview image storage ---


class ProjectPreviewStorageTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.projects_dir = Path(self.temp_dir.name) / "projects"
        self.projects_patch = patch.object(
            project_service,
            "PROJECTS_DIR",
            self.projects_dir,
        )
        self.projects_patch.start()
        self.addCleanup(self.projects_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def test_create_persists_preview_and_lists_it_for_project_cards(self):
        project = project_service.create_project(
            "user-1",
            {
                "title": "Preview test",
                "editorState": {
                    "components": [],
                    "previewImage": JPEG_PREVIEW,
                },
            },
        )

        stored_project = json.loads(
            (self.projects_dir / "user-1" / project["id"] / "project.json").read_text(
                encoding="utf-8"
            )
        )
        listed_project = project_service.list_projects("user-1")[0]

        self.assertEqual(stored_project["previewImage"], JPEG_PREVIEW)
        self.assertEqual(stored_project["editorState"]["previewImage"], JPEG_PREVIEW)
        self.assertEqual(listed_project["previewImage"], JPEG_PREVIEW)

    def test_list_projects_reads_previews_from_legacy_editor_state(self):
        project = project_service.create_project(
            "user-1",
            {
                "title": "Legacy preview",
                "editorState": {
                    "components": [],
                    "previewImage": JPEG_PREVIEW,
                },
            },
        )
        project_path = self.projects_dir / "user-1" / project["id"] / "project.json"
        stored_project = json.loads(project_path.read_text(encoding="utf-8"))
        stored_project.pop("previewImage")
        project_path.write_text(
            json.dumps(stored_project),
            encoding="utf-8",
        )

        listed_project = project_service.list_projects("user-1")[0]

        self.assertEqual(listed_project["previewImage"], JPEG_PREVIEW)

    def test_update_refreshes_preview_and_title_only_update_preserves_it(self):
        project = project_service.create_project(
            "user-1",
            {"title": "Preview test", "previewImage": JPEG_PREVIEW},
        )
        updated_preview = "data:image/jpeg;base64," + base64.b64encode(
            b"\xff\xd8\xff\xe0"
        ).decode("ascii")

        updated_project = project_service.update_project(
            "user-1",
            project["id"],
            {
                "editorState": {"components": [], "previewImage": updated_preview},
            },
        )
        renamed_project = project_service.update_project(
            "user-1",
            project["id"],
            {"title": "Renamed"},
        )

        assert updated_project is not None
        assert renamed_project is not None
        self.assertEqual(updated_project["previewImage"], updated_preview)
        self.assertEqual(renamed_project["previewImage"], updated_preview)
        self.assertEqual(
            project_service.list_projects("user-1")[0]["previewImage"],
            updated_preview,
        )

    def test_rejects_invalid_preview_data_urls(self):
        with self.assertRaises(ValueError):
            project_service.create_project(
                "user-1",
                {
                    "title": "Invalid preview",
                    "previewImage": "data:image/svg+xml;base64,PHN2Zz4=",
                },
            )


class RequestValidationHandlerTests(unittest.TestCase):
    def _make_client(self) -> TestClient:
        from fastapi.exceptions import RequestValidationError

        from app.api.auth_routes import router as auth_router
        from app.main import request_validation_exception_handler

        app = FastAPI()
        app.add_exception_handler(
            RequestValidationError,
            request_validation_exception_handler,  # type: ignore[arg-type]
        )
        app.include_router(auth_router)
        app.include_router(projects_router)
        app.dependency_overrides[auth_service.get_current_active_user] = lambda: (
            auth_service.User(id="user-1", email="user-1@example.com")
        )
        return TestClient(app)

    def test_formats_missing_fields_and_model_validator_value_errors_as_string(self):
        from fastapi.exceptions import RequestValidationError

        from app.main import app as main_app
        from app.main import request_validation_exception_handler

        self.assertIs(
            main_app.exception_handlers.get(RequestValidationError),
            request_validation_exception_handler,
        )

        client = self._make_client()

        missing_resp = client.post("/auth/register", json={"password": "secret123"})
        self.assertEqual(missing_resp.status_code, 422)
        missing_body = missing_resp.json()
        self.assertIsInstance(missing_body["detail"], str)
        self.assertIn("email:", missing_body["detail"])
        self.assertIsInstance(missing_body["errors"], list)
        self.assertEqual(missing_body["errors"][0]["loc"], ["body", "email"])

        # Triggers @model_validator ValueError (raw ctx holds non-JSON ValueError).
        bad_schema = make_valid_schema()
        bad_schema["views"][0]["pageId"] = "non-existent-page"
        validator_resp = client.post("/projects", json={"schema": bad_schema})
        self.assertEqual(validator_resp.status_code, 422)
        validator_body = validator_resp.json()
        self.assertIsInstance(validator_body["detail"], str)
        self.assertIn("does not exist", validator_body["detail"])
        self.assertNotIn("Value error, ", validator_body["detail"])
        self.assertEqual(validator_body["errors"][0]["type"], "value_error")

        overflow_resp = client.post(
            "/projects",
            json={
                "title": 1,
                "description": 2,
                "previewImage": 3,
                "datasets": "not-a-list",
            },
        )
        self.assertEqual(overflow_resp.status_code, 422)
        overflow_body = overflow_resp.json()
        self.assertEqual(len(overflow_body["errors"]), 4)
        self.assertIn("(+1 more)", overflow_body["detail"])


if __name__ == "__main__":
    unittest.main()
