import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.services import project_service


PREVIEW_IMAGE = (
    "data:image/jpeg;base64,"
    + base64.b64encode(b"\xff\xd8\xff\xdb").decode("ascii")
)


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
                    "previewImage": PREVIEW_IMAGE,
                },
            },
        )

        stored_project = json.loads(
            (self.projects_dir / "user-1" / project["id"] / "project.json")
            .read_text(encoding="utf-8")
        )
        listed_project = project_service.list_projects("user-1")[0]

        self.assertEqual(stored_project["previewImage"], PREVIEW_IMAGE)
        self.assertEqual(stored_project["editorState"]["previewImage"], PREVIEW_IMAGE)
        self.assertEqual(listed_project["previewImage"], PREVIEW_IMAGE)

    def test_list_projects_reads_previews_from_legacy_editor_state(self):
        project = project_service.create_project(
            "user-1",
            {
                "title": "Legacy preview",
                "editorState": {
                    "components": [],
                    "previewImage": PREVIEW_IMAGE,
                },
            },
        )
        project_path = (
            self.projects_dir / "user-1" / project["id"] / "project.json"
        )
        stored_project = json.loads(project_path.read_text(encoding="utf-8"))
        stored_project.pop("previewImage")
        project_path.write_text(
            json.dumps(stored_project),
            encoding="utf-8",
        )

        listed_project = project_service.list_projects("user-1")[0]

        self.assertEqual(listed_project["previewImage"], PREVIEW_IMAGE)

    def test_update_refreshes_preview_and_title_only_update_preserves_it(self):
        project = project_service.create_project(
            "user-1",
            {"title": "Preview test", "previewImage": PREVIEW_IMAGE},
        )
        updated_preview = (
            "data:image/jpeg;base64,"
            + base64.b64encode(b"\xff\xd8\xff\xe0").decode("ascii")
        )

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
