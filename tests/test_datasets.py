import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient

from app.api.datasets_routes import router as datasets_router
from app.services import auth_service, dataset_service


class DatasetTests(unittest.TestCase):
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

    def _make_upload_file(self, filename: str, content: bytes) -> UploadFile:
        return UploadFile(filename=filename, file=io.BytesIO(content))

    def _make_excel_bytes(self, sheets: dict[str, pd.DataFrame]) -> bytes:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            for sheet_name, frame in sheets.items():
                frame.to_excel(writer, sheet_name=sheet_name, index=False)
        return buffer.getvalue()

    def _make_client(self, user_id: str | None = "user-1") -> TestClient:
        app = FastAPI()
        app.include_router(datasets_router)
        if user_id is not None:
            app.dependency_overrides[auth_service.get_current_active_user] = lambda: (
                auth_service.User(
                    id=user_id,
                    email=f"{user_id}@example.com",
                )
            )
        return TestClient(app)

    def _upload_csv(
        self,
        client: TestClient,
        content: bytes,
        filename: str = "data.csv",
        form_data: dict[str, str] | None = None,
    ):
        return client.post(
            "/datasets/upload",
            files={"dataset": (filename, content, "text/csv")},
            data=form_data or {},
        )

    def _write_csv_dataset(
        self,
        user_id: str,
        dataset_id: str,
        content: str,
    ) -> None:
        data_dir = self.datasets_dir / user_id / dataset_id
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "data.csv").write_text(content, encoding="utf-8")

    # --- Upload (POST /datasets/upload) ---

    def test_upload_csv_sanitizes_custom_name_and_infers_all_field_types(self):
        client = self._make_client("user-1")
        csv_bytes = (
            b"active,sales,created_at,region\n"
            b"true,100,2026-01-10,North\n"
            b"false,250,2026-01-11,South\n"
        )

        response = self._upload_csv(
            client,
            csv_bytes,
            filename="raw.csv",
            form_data={"name": 'sales/2026:Q1*"report"'},
        )

        self.assertEqual(response.status_code, 200)
        meta = response.json()
        self.assertEqual(meta["userId"], "user-1")
        self.assertEqual(meta["name"], "sales_2026_Q1__report_.csv")
        self.assertEqual(meta["format"], "csv")
        self.assertEqual(meta["fields"], ["active", "sales", "created_at", "region"])
        self.assertEqual(
            meta["fieldTypes"],
            {
                "active": "boolean",
                "sales": "number",
                "created_at": "datetime",
                "region": "string",
            },
        )
        self.assertGreater(meta["size"], 0)
        self.assertTrue(meta["createdAt"])

    def test_upload_excel_uses_sheet_name_alias_and_falls_back_on_unknown_sheet(self):
        client = self._make_client("user-1")
        excel_bytes = self._make_excel_bytes(
            {
                "SheetA": pd.DataFrame({"a": [1, 2]}),
                "SheetB": pd.DataFrame({"b": [3, 4]}),
            }
        )

        explicit = client.post(
            "/datasets/upload",
            files={"dataset": ("report.xlsx", excel_bytes)},
            data={"name": "custom_report", "sheetName": "SheetB"},
        )
        self.assertEqual(explicit.status_code, 200)
        explicit_meta = explicit.json()
        self.assertEqual(explicit_meta["name"], "custom_report.xlsx")
        self.assertEqual(explicit_meta["sheetName"], "SheetB")
        self.assertEqual(explicit_meta["fields"], ["b"])

        preview = client.get(f"/datasets/{explicit_meta['datasetId']}/preview")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["rows"][0]["b"], 3)

        fallback = client.post(
            "/datasets/upload",
            files={"dataset": ("report.xlsx", excel_bytes)},
            data={"sheetName": "NonExistentSheet"},
        )
        self.assertEqual(fallback.status_code, 200)
        self.assertEqual(fallback.json()["sheetName"], "SheetA")
        self.assertEqual(fallback.json()["fields"], ["a"])

    def test_upload_corrupted_file_returns_400_and_cleans_up_directory(self):
        client = self._make_client("user-1")

        corrupted = client.post(
            "/datasets/upload",
            files={"dataset": ("broken.xlsx", b"not-a-valid-excel-archive")},
        )
        invalid_name = self._upload_csv(
            client,
            b"a,b\n1,2\n",
            form_data={"name": "bad\x00name"},
        )

        self.assertEqual(corrupted.status_code, 400)
        self.assertEqual(invalid_name.status_code, 400)
        user_dir = self.datasets_dir / "user-1"
        leftover_dirs = list(user_dir.iterdir()) if user_dir.exists() else []
        self.assertEqual(leftover_dirs, [])

    # --- Read metadata & user isolation (GET /datasets/{dataset_id}) ---

    def test_get_dataset_meta_returns_owner_meta_and_hides_foreign_or_missing(self):
        owner_client = self._make_client("user-1")
        other_client = self._make_client("user-2")
        uploaded = self._upload_csv(owner_client, b"region,sales\nA,10\n").json()
        dataset_id = uploaded["datasetId"]

        owner_response = owner_client.get(f"/datasets/{dataset_id}")
        foreign_response = other_client.get(f"/datasets/{dataset_id}")
        missing_response = owner_client.get("/datasets/missing-id")

        self.assertEqual(owner_response.status_code, 200)
        self.assertEqual(owner_response.json()["datasetId"], dataset_id)
        self.assertEqual(foreign_response.status_code, 404)
        self.assertEqual(missing_response.status_code, 404)

    # --- Preview (GET /datasets/{dataset_id}/preview) ---

    def test_returns_rows_for_live_canvas(self):
        self._write_csv_dataset("user-1", "dataset-1", "region,sales\nA,10\nB,20\n")

        preview = dataset_service.get_dataset_preview("user-1", "dataset-1", limit=100)

        assert preview is not None
        self.assertEqual(preview["returnedRows"], 2)
        self.assertEqual(preview["fieldTypes"]["sales"], "number")
        self.assertEqual(preview["rows"][1]["region"], "B")

    def test_preview_api_respects_limit_bounds_and_user_isolation(self):
        owner_client = self._make_client("user-1")
        other_client = self._make_client("user-2")
        csv_bytes = b"region,sales\nA,10\nB,20\nC,30\nD,40\n"
        dataset_id = self._upload_csv(owner_client, csv_bytes).json()["datasetId"]

        limited = owner_client.get(f"/datasets/{dataset_id}/preview?limit=2")
        self.assertEqual(limited.status_code, 200)
        body = limited.json()
        self.assertEqual(body["returnedRows"], 2)
        self.assertEqual(len(body["rows"]), 2)
        self.assertEqual(body["rows"][0]["sales"], 10)

        self.assertEqual(
            owner_client.get(f"/datasets/{dataset_id}/preview?limit=0").status_code,
            422,
        )
        self.assertEqual(
            owner_client.get(f"/datasets/{dataset_id}/preview?limit=10001").status_code,
            422,
        )
        self.assertEqual(
            other_client.get(f"/datasets/{dataset_id}/preview").status_code,
            404,
        )
        self.assertEqual(
            owner_client.get("/datasets/missing-id/preview").status_code,
            404,
        )

    def test_preview_api_returns_400_for_corrupted_stored_file(self):
        data_dir = self.datasets_dir / "user-1" / "broken-ds"
        data_dir.mkdir(parents=True, exist_ok=True)
        (data_dir / "broken.xlsx").write_bytes(b"corrupted-bytes")
        (data_dir / "meta.json").write_text(
            json.dumps(
                {
                    "datasetId": "broken-ds",
                    "name": "broken.xlsx",
                    "format": "excel",
                    "sheetName": "Sheet1",
                }
            ),
            encoding="utf-8",
        )
        client = self._make_client("user-1")

        response = client.get("/datasets/broken-ds/preview")
        self.assertEqual(response.status_code, 400)

    # --- File formats, delimiters, and encodings ---

    def test_save_and_preview_tsv(self):
        upload_file = self._make_upload_file("data.tsv", b"col1\tcol2\n10\t20\n")

        saved = dataset_service.save_dataset(
            user_id="user-1",
            file=upload_file,
            delimiter="\t",
        )
        self.assertEqual(saved["format"], "tsv")
        self.assertEqual(saved["delimiter"], "\t")

        preview = dataset_service.get_dataset_preview("user-1", saved["datasetId"])
        assert preview is not None
        self.assertEqual(preview["fields"], ["col1", "col2"])
        self.assertEqual(preview["rows"][0]["col1"], 10)

    def test_save_and_preview_cp1251_csv(self):
        csv_text = "город;продажи\nМосква;150\nСанкт-Петербург;230\n"
        upload_file = self._make_upload_file(
            "sales_cp1251.csv",
            csv_text.encode("cp1251"),
        )

        saved = dataset_service.save_dataset(user_id="user-1", file=upload_file)
        self.assertEqual(saved["format"], "csv")
        self.assertEqual(saved["delimiter"], ";")
        self.assertEqual(saved["encoding"], "cp1251")
        self.assertEqual(saved["fields"], ["город", "продажи"])

        preview = dataset_service.get_dataset_preview("user-1", saved["datasetId"])
        assert preview is not None
        self.assertEqual(preview["fields"], ["город", "продажи"])
        self.assertEqual(preview["rows"][0]["город"], "Москва")
        self.assertEqual(preview["rows"][0]["продажи"], 150)

    def test_save_and_preview_utf8_sig_csv(self):
        csv_text = "клиент,сумма\nИван,500\nОльга,900\n"
        upload_file = self._make_upload_file(
            "clients_bom.csv",
            csv_text.encode("utf-8-sig"),
        )

        saved = dataset_service.save_dataset(user_id="user-1", file=upload_file)
        self.assertEqual(saved["format"], "csv")
        self.assertEqual(saved["encoding"], "utf-8-sig")
        self.assertEqual(saved["fields"], ["клиент", "сумма"])

        preview = dataset_service.get_dataset_preview("user-1", saved["datasetId"])
        assert preview is not None
        self.assertEqual(preview["fields"], ["клиент", "сумма"])
        self.assertEqual(preview["rows"][0]["клиент"], "Иван")

    def test_save_and_preview_utf16_le_csv(self):
        csv_text = "город;продажи\nМосква;150\nКазань;320\n"
        upload_file = self._make_upload_file(
            "sales_utf16.csv",
            b"\xff\xfe" + csv_text.encode("utf-16-le"),
        )

        saved = dataset_service.save_dataset(user_id="user-1", file=upload_file)
        self.assertEqual(saved["format"], "csv")
        self.assertEqual(saved["encoding"], "utf-16-le")
        self.assertEqual(saved["delimiter"], ";")
        self.assertEqual(saved["fields"], ["город", "продажи"])

        preview = dataset_service.get_dataset_preview("user-1", saved["datasetId"])
        assert preview is not None
        self.assertEqual(preview["fields"], ["город", "продажи"])
        self.assertEqual(preview["rows"][0]["город"], "Москва")
        self.assertEqual(preview["rows"][0]["продажи"], 150)

    # --- Delete (DELETE /datasets/{dataset_id}) ---

    def test_delete_removes_owner_dataset_and_blocks_other_user(self):
        owner_client = self._make_client("user-1")
        other_client = self._make_client("user-2")
        dataset_id = self._upload_csv(owner_client, b"a,b\n1,2\n").json()["datasetId"]
        dataset_dir = self.datasets_dir / "user-1" / dataset_id
        self.assertTrue(dataset_dir.exists())

        foreign_delete = other_client.delete(f"/datasets/{dataset_id}")
        self.assertEqual(foreign_delete.status_code, 404)
        self.assertTrue(dataset_dir.exists())

        owner_delete = owner_client.delete(f"/datasets/{dataset_id}")
        self.assertEqual(owner_delete.status_code, 200)
        self.assertEqual(owner_delete.json(), {"deleted": True})
        self.assertFalse(dataset_dir.exists())
        self.assertEqual(owner_client.get(f"/datasets/{dataset_id}").status_code, 404)
        self.assertEqual(
            owner_client.delete(f"/datasets/{dataset_id}").status_code,
            404,
        )

    # --- Excel sheet inspection (POST /datasets/inspect-sheets) ---

    def test_inspect_sheets_returns_sheet_names_and_rejects_invalid_files(self):
        client = self._make_client("user-1")
        excel_bytes = self._make_excel_bytes(
            {
                "SheetA": pd.DataFrame({"a": [1]}),
                "SheetB": pd.DataFrame({"b": [2]}),
            }
        )

        valid = client.post(
            "/datasets/inspect-sheets",
            files={"file": ("book.xlsx", excel_bytes)},
        )
        non_excel = client.post(
            "/datasets/inspect-sheets",
            files={"file": ("plain.csv", b"a,b\n1,2\n")},
        )
        corrupted = client.post(
            "/datasets/inspect-sheets",
            files={"file": ("broken.xlsx", b"not-excel-bytes")},
        )

        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.json(), {"sheets": ["SheetA", "SheetB"]})
        self.assertEqual(non_excel.status_code, 400)
        self.assertEqual(corrupted.status_code, 400)

    # --- Authentication & path traversal protection ---

    def test_unauthenticated_requests_return_401(self):
        client = self._make_client(user_id=None)

        self.assertEqual(
            client.post(
                "/datasets/upload",
                files={"dataset": ("data.csv", b"a\n1\n")},
            ).status_code,
            401,
        )
        self.assertEqual(client.get("/datasets/some-id").status_code, 401)
        self.assertEqual(client.get("/datasets/some-id/preview").status_code, 401)
        self.assertEqual(client.delete("/datasets/some-id").status_code, 401)
        self.assertEqual(
            client.post(
                "/datasets/inspect-sheets",
                files={"file": ("book.xlsx", b"bytes")},
            ).status_code,
            401,
        )

    def test_path_traversal_dataset_id_is_rejected_without_touching_other_users(self):
        victim_client = self._make_client("user-2")
        attacker_client = self._make_client("user-1")
        victim_id = self._upload_csv(victim_client, b"secret,val\nx,42\n").json()[
            "datasetId"
        ]
        victim_dir = self.datasets_dir / "user-2" / victim_id
        self.assertTrue(victim_dir.exists())

        # URL-encoded slash reaches FastAPI as dataset_id="../user-2"
        self.assertEqual(
            attacker_client.get(f"/datasets/..%2Fuser-2%2F{victim_id}").status_code,
            404,
        )
        self.assertEqual(
            attacker_client.get(
                f"/datasets/..%2Fuser-2%2F{victim_id}/preview"
            ).status_code,
            404,
        )
        self.assertEqual(
            attacker_client.delete("/datasets/..%2Fuser-2").status_code,
            404,
        )
        # Direct service-level traversal attempts (POSIX & Windows separators)
        self.assertIsNone(
            dataset_service.get_dataset_meta("user-1", f"../user-2/{victim_id}")
        )
        self.assertIsNone(
            dataset_service.get_dataset_path("user-1", f"..\\user-2\\{victim_id}")
        )
        self.assertFalse(dataset_service.delete_dataset("user-1", "../user-2"))
        self.assertFalse(dataset_service.delete_dataset("user-1", "..\\user-2"))
        self.assertTrue(victim_dir.exists())


if __name__ == "__main__":
    unittest.main()
