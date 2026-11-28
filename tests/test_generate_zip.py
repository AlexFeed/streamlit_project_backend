import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient

from app.api.generate_routes import router as generate_router
from app.services import auth_service, dataset_service


def make_export_schema(data_sources: list[dict]) -> dict:
    primary_id = data_sources[0].get("datasetId")
    return {
        "version": 2,
        "dashboard": {
            "title": "Exported dashboard",
            "grid": {"columns": 12},
        },
        "dataSources": data_sources,
        "filters": [],
        "views": [
            {
                "id": "metric-1",
                "type": "metric",
                "datasetId": primary_id,
                "order": 1,
                "layout": {"width": 4, "height": 160},
                "title": "Total",
                "field": "sales",
                "aggregation": "sum",
            }
        ],
    }


class GenerateZipRouteTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.datasets_dir = Path(self.temp_dir.name)
        self.datasets_patch = patch.object(
            dataset_service,
            "DATASETS_DIR",
            self.datasets_dir,
        )
        self.datasets_patch.start()
        self.addCleanup(self.datasets_patch.stop)
        self.addCleanup(self.temp_dir.cleanup)

    def _make_client(self, user_id: str | None = "user-1") -> TestClient:
        app = FastAPI()
        app.include_router(generate_router)
        if user_id is not None:
            app.dependency_overrides[auth_service.get_current_active_user] = lambda: (
                auth_service.User(id=user_id, email=f"{user_id}@example.com")
            )
        return TestClient(app)

    def _save_csv(
        self,
        user_id: str,
        filename: str,
        content: bytes,
    ) -> dict:
        upload = UploadFile(filename=filename, file=io.BytesIO(content))
        return dataset_service.save_dataset(user_id=user_id, file=upload)

    def _save_excel(
        self,
        user_id: str,
        filename: str,
        sheets: dict[str, pd.DataFrame],
        sheet_name: str,
    ) -> dict:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for name, frame in sheets.items():
                frame.to_excel(writer, sheet_name=name, index=False)
        upload = UploadFile(filename=filename, file=io.BytesIO(buffer.getvalue()))
        return dataset_service.save_dataset(
            user_id=user_id,
            file=upload,
            sheet_name=sheet_name,
        )

    # --- Successful ZIP assembly ---

    def test_generates_valid_zip_bundle_for_csv_dataset(self):
        csv_bytes = b"region,sales\nA,10\nB,25\n"
        meta = self._save_csv("user-1", "sales.csv", csv_bytes)
        schema = make_export_schema(
            [
                {
                    "type": "backend_dataset",
                    "datasetId": meta["datasetId"],
                    "name": meta["name"],
                    "format": "csv",
                }
            ]
        )

        response = self._make_client("user-1").post(
            "/generate",
            json={"schema": schema},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/zip")
        self.assertIn(
            "dashboard_project.zip",
            response.headers["content-disposition"],
        )

        with zipfile.ZipFile(io.BytesIO(response.content), "r") as archive:
            names = set(archive.namelist())
            self.assertEqual(
                names,
                {
                    "app.py",
                    "data/sales.csv",
                    "requirements.txt",
                    "README.md",
                    "run_local.bat",
                    "run_local.sh",
                },
            )
            app_code = archive.read("app.py").decode("utf-8")
            compile(app_code, "app.py", "exec")
            self.assertEqual(archive.read("data/sales.csv"), csv_bytes)

            requirements = archive.read("requirements.txt").decode("utf-8")
            self.assertIn("streamlit", requirements)
            self.assertIn("pandas", requirements)
            self.assertNotIn("openpyxl", requirements)
            self.assertTrue(
                archive.read("run_local.sh")
                .decode("utf-8")
                .startswith("#!/usr/bin/env bash\n")
            )

    def test_excel_export_includes_openpyxl_and_sheet_name(self):
        meta = self._save_excel(
            "user-1",
            "report.xlsx",
            {
                "Summary": pd.DataFrame({"sales": [10]}),
                "Details": pd.DataFrame({"sales": [42, 58]}),
            },
            sheet_name="Details",
        )
        schema = make_export_schema(
            [
                {
                    "type": "backend_dataset",
                    "datasetId": meta["datasetId"],
                    "name": meta["name"],
                    "format": "excel",
                    "sheetName": "Details",
                }
            ]
        )

        response = self._make_client("user-1").post(
            "/generate",
            json={"schema": schema},
        )

        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.content), "r") as archive:
            self.assertIn("data/report.xlsx", archive.namelist())
            requirements = archive.read("requirements.txt").decode("utf-8")
            self.assertIn("openpyxl", requirements)
            app_code = archive.read("app.py").decode("utf-8")
            compile(app_code, "app.py", "exec")
            self.assertIn("'sheetName': 'Details'", app_code)

    def test_disambiguates_duplicate_dataset_filenames_in_zip(self):
        first = self._save_csv("user-1", "sales.csv", b"region,sales\nA,10\n")
        second = self._save_csv("user-1", "sales.csv", b"region,sales\nB,99\n")
        schema = make_export_schema(
            [
                {
                    "type": "backend_dataset",
                    "datasetId": first["datasetId"],
                    "name": first["name"],
                },
                {
                    "type": "backend_dataset",
                    "datasetId": second["datasetId"],
                    "name": second["name"],
                },
            ]
        )

        response = self._make_client("user-1").post(
            "/generate",
            json={"schema": schema},
        )

        self.assertEqual(response.status_code, 200)
        expected_second_name = f"{second['datasetId']}_sales.csv"
        with zipfile.ZipFile(io.BytesIO(response.content), "r") as archive:
            names = set(archive.namelist())
            self.assertIn("data/sales.csv", names)
            self.assertIn(f"data/{expected_second_name}", names)
            self.assertEqual(archive.read("data/sales.csv"), b"region,sales\nA,10\n")
            self.assertEqual(
                archive.read(f"data/{expected_second_name}"),
                b"region,sales\nB,99\n",
            )
            app_code = archive.read("app.py").decode("utf-8")
            self.assertIn(expected_second_name, app_code)

    # --- Validation, missing resources, and user isolation ---

    def test_rejects_missing_schema_with_422(self):
        response = self._make_client("user-1").post("/generate", json={})
        self.assertEqual(response.status_code, 422)

    def test_rejects_invalid_schema_with_422(self):
        response = self._make_client("user-1").post(
            "/generate",
            json={"schema": {"version": 2, "dashboard": {"title": "Broken"}}},
        )
        self.assertEqual(response.status_code, 422)

    def test_rejects_data_source_without_dataset_id_with_400(self):
        schema = make_export_schema([{"type": "backend_dataset", "name": "sales.csv"}])
        response = self._make_client("user-1").post(
            "/generate",
            json={"schema": schema},
        )
        self.assertEqual(response.status_code, 400)

    def test_returns_404_for_missing_or_foreign_user_dataset(self):
        meta = self._save_csv("user-1", "sales.csv", b"region,sales\nA,10\n")
        schema = make_export_schema(
            [
                {
                    "type": "backend_dataset",
                    "datasetId": meta["datasetId"],
                    "name": meta["name"],
                }
            ]
        )

        # Another user must not be able to export user-1's dataset.
        foreign_response = self._make_client("user-2").post(
            "/generate",
            json={"schema": schema},
        )
        self.assertEqual(foreign_response.status_code, 404)

        missing_schema = make_export_schema(
            [
                {
                    "type": "backend_dataset",
                    "datasetId": "nonexistent-dataset",
                    "name": "sales.csv",
                }
            ]
        )
        missing_response = self._make_client("user-1").post(
            "/generate",
            json={"schema": missing_schema},
        )
        self.assertEqual(missing_response.status_code, 404)

    def test_unauthenticated_generate_returns_401(self):
        response = self._make_client(user_id=None).post("/generate", json={})
        self.assertEqual(response.status_code, 401)

    def test_build_dashboard_zip_raises_domain_errors_and_keeps_input_unchanged(self):
        from app.services.generator_service import (
            DatasetNotFoundError,
            build_dashboard_zip,
        )

        with self.assertRaises(ValueError):
            build_dashboard_zip("user-1", {"dataSources": []})

        with self.assertRaises(DatasetNotFoundError):
            build_dashboard_zip(
                "user-1",
                make_export_schema(
                    [{"type": "backend_dataset", "datasetId": "missing"}]
                ),
            )

        first = self._save_csv("user-1", "sales.csv", b"region,sales\nA,10\n")
        second = self._save_csv("user-1", "sales.csv", b"region,sales\nB,20\n")
        schema = make_export_schema(
            [
                {
                    "type": "backend_dataset",
                    "datasetId": first["datasetId"],
                    "name": "original.csv",
                },
                {
                    "type": "backend_dataset",
                    "datasetId": second["datasetId"],
                    "name": "original.csv",
                },
            ]
        )

        build_dashboard_zip("user-1", schema)
        self.assertEqual(schema["dataSources"][1]["name"], "original.csv")


if __name__ == "__main__":
    unittest.main()
