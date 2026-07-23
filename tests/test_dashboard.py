import ast
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.datasets_routes import router as datasets_router
from app.schemas.dashboard import validate_dashboard_schema
from app.services.generator_service import generate_streamlit_code
from app.services import auth_service, dataset_service
from app.services.preview_service import PreviewService
from app.services.renderers.data_transform import (
    calculate_metric,
    prepare_chart_data,
)
from app.services.renderers.schema_utils import (
    balance_components_by_height,
    get_components,
    get_row_column_widths,
    pack_component_rows,
)
from app.services.renderers import preview_runtime_render


def make_schema() -> dict:
    return {
        "version": 2,
        "dashboard": {
            "title": "Sales dashboard",
            "grid": {"columns": 12},
        },
        "dataSource": {
            "type": "backend_dataset",
            "datasetId": "dataset-1",
            "name": "sales.csv",
            "fields": ["date", "region", "sales"],
        },
        "filters": [
            {
                "id": "filter-1",
                "type": "selectbox",
                "order": 1,
                "layout": {"width": 4, "height": 160},
                "title": "Region",
                "field": "region",
                "scope": "global",
            }
        ],
        "views": [
            {
                "id": "chart-1",
                "type": "area_chart",
                "order": 2,
                "layout": {"width": 8, "height": 360},
                "title": "Sales trend",
                "x": "date",
                "y": "sales",
                "aggregation": "sum",
                "sort": "asc",
                "sortBy": "x",
                "color": "#818cf8",
            },
            {
                "id": "metric-1",
                "type": "metric",
                "order": 3,
                "layout": {"width": 4, "height": 200},
                "title": "Total",
                "description": "",
                "field": "sales",
                "aggregation": "sum",
            },
        ],
    }


class DashboardSchemaTests(unittest.TestCase):
    def test_validates_schema_v2(self):
        schema = validate_dashboard_schema(make_schema())

        self.assertEqual(schema["version"], 2)
        self.assertEqual(schema["views"][0]["layout"]["width"], 8)
        self.assertEqual(schema["views"][0]["layout"]["height"], 360)
        self.assertEqual(schema["views"][0]["color"], "#818cf8")
        self.assertEqual(schema["dataSource"]["datasetId"], "dataset-1")

    def test_rejects_invalid_width(self):
        schema = make_schema()
        schema["views"][0]["layout"]["width"] = 0

        with self.assertRaises(ValidationError):
            validate_dashboard_schema(schema)

    def test_accepts_freeform_width_and_position(self):
        schema = make_schema()
        schema["views"][0]["layout"].update({
            "x": 5,
            "y": 7,
            "width": 5,
        })

        validated = validate_dashboard_schema(schema)

        self.assertEqual(
            validated["views"][0]["layout"],
            {"width": 5, "height": 360, "x": 5, "y": 7},
        )

    def test_rejects_duplicate_component_ids(self):
        schema = make_schema()
        schema["views"][0]["id"] = "filter-1"

        with self.assertRaises(ValueError):
            validate_dashboard_schema(schema)

    def test_rejects_invalid_chart_color(self):
        schema = make_schema()
        schema["views"][0]["color"] = "purple"

        with self.assertRaises(ValidationError):
            validate_dashboard_schema(schema)

    def test_validates_gradient_palette(self):
        schema = make_schema()
        schema["views"][0].update({
            "type": "bar_chart",
            "colorMode": "gradient",
            "palette": ["#fbbf24", "#f97316", "#ef4444"],
        })

        validated = validate_dashboard_schema(schema)

        self.assertEqual(validated["views"][0]["colorMode"], "gradient")
        self.assertEqual(validated["views"][0]["palette"][-1], "#ef4444")

    def test_rejects_invalid_palette_color(self):
        schema = make_schema()
        schema["views"][0]["palette"] = ["#3b82f6", "orange"]

        with self.assertRaises(ValidationError):
            validate_dashboard_schema(schema)

    def test_rejects_gradient_for_single_series_line_chart(self):
        schema = make_schema()
        schema["views"][0].update({
            "type": "line_chart",
            "colorMode": "gradient",
        })

        with self.assertRaises(ValidationError):
            validate_dashboard_schema(schema)


class LayoutTests(unittest.TestCase):
    def test_packs_components_into_twelve_column_rows(self):
        components = [
            {"layout": {"width": 8}},
            {"layout": {"width": 4}},
            {"layout": {"width": 6}},
        ]

        rows = pack_component_rows(components)

        self.assertEqual([len(row) for row in rows], [2, 1])
        self.assertEqual(get_row_column_widths(rows[0]), [8, 4])
        self.assertEqual(get_row_column_widths(rows[1]), [6, 6])

    def test_keeps_filters_and_views_in_one_ordered_grid(self):
        components = get_components(make_schema())
        rows = pack_component_rows(components)

        self.assertEqual(
            [component["type"] for component in components],
            ["selectbox", "area_chart", "metric"],
        )
        self.assertEqual(get_row_column_widths(rows[0]), [4, 8])
        self.assertEqual(get_row_column_widths(rows[1]), [4, 8])

    def test_balances_charts_by_individual_height(self):
        components = [
            {"id": "chart-1", "layout": {"height": 280}},
            {"id": "chart-2", "layout": {"height": 220}},
            {"id": "chart-3", "layout": {"height": 260}},
            {"id": "chart-4", "layout": {"height": 380}},
        ]

        lanes = balance_components_by_height(components)

        self.assertEqual(
            [[component["id"] for component in lane] for lane in lanes],
            [["chart-1", "chart-4"], ["chart-2", "chart-3"]],
        )


class DataTransformTests(unittest.TestCase):
    def setUp(self):
        self.dataframe = pd.DataFrame({
            "region": ["A", "A", "B"],
            "sales": [10, 15, 7],
        })

    def test_aggregates_and_sorts_chart_data(self):
        result = prepare_chart_data(self.dataframe, {
            "x": "region",
            "y": "sales",
            "aggregation": "sum",
            "sort": "desc",
        })

        self.assertEqual(result["region"].tolist(), ["B", "A"])
        self.assertEqual(result["sales"].tolist(), [7, 25])

    def test_sorts_chart_by_aggregated_y_value(self):
        result = prepare_chart_data(self.dataframe, {
            "x": "region",
            "y": "sales",
            "aggregation": "sum",
            "sort": "desc",
            "sortBy": "y",
        })

        self.assertEqual(result["region"].tolist(), ["A", "B"])
        self.assertEqual(result["sales"].tolist(), [25, 7])

    def test_calculates_metric(self):
        self.assertEqual(
            calculate_metric(self.dataframe, "sales", "sum"),
            32,
        )
        self.assertEqual(
            calculate_metric(self.dataframe, "sales", "count"),
            3,
        )

    def test_counts_non_numeric_chart_values(self):
        result = prepare_chart_data(pd.DataFrame({
            "region": ["A", "A", "B"],
            "order": ["first", "second", "third"],
        }), {
            "x": "region",
            "y": "order",
            "aggregation": "count",
            "sort": "asc",
        })

        self.assertEqual(result["order"].tolist(), [2, 1])

    def test_supports_every_chart_aggregation(self):
        expected_values = {
            "sum": [25, 7],
            "mean": [12.5, 7.0],
            "count": [2, 1],
            "min": [10, 7],
            "max": [15, 7],
        }

        for aggregation, expected in expected_values.items():
            with self.subTest(aggregation=aggregation):
                result = prepare_chart_data(self.dataframe, {
                    "x": "region",
                    "y": "sales",
                    "aggregation": aggregation,
                    "sort": "asc",
                })

                self.assertEqual(result["region"].tolist(), ["A", "B"])
                self.assertEqual(result["sales"].tolist(), expected)


class DatasetPreviewTests(unittest.TestCase):
    def test_returns_rows_for_live_canvas(self):
        with tempfile.TemporaryDirectory() as directory:
            datasets_dir = Path(directory)
            data_dir = datasets_dir / "user-1" / "dataset-1"
            data_dir.mkdir(parents=True)
            (data_dir / "data.csv").write_text(
                "region,sales\nA,10\nB,20\n",
                encoding="utf-8",
            )

            with patch.object(dataset_service, "DATASETS_DIR", datasets_dir):
                preview = dataset_service.get_dataset_preview(
                    "user-1",
                    "dataset-1",
                    limit=100,
                )

            self.assertEqual(preview["returnedRows"], 2)
            self.assertEqual(preview["fieldTypes"]["sales"], "number")
            self.assertEqual(preview["rows"][1]["region"], "B")

    def test_preview_api_returns_live_canvas_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            datasets_dir = Path(directory)
            data_dir = datasets_dir / "user-1" / "dataset-1"
            data_dir.mkdir(parents=True)
            (data_dir / "data.csv").write_text(
                "region,sales\nA,10\nB,20\n",
                encoding="utf-8",
            )

            app = FastAPI()
            app.include_router(datasets_router)
            app.dependency_overrides[
                auth_service.get_current_active_user
            ] = lambda: auth_service.User(
                id="user-1",
                email="test@example.com",
            )

            with patch.object(dataset_service, "DATASETS_DIR", datasets_dir):
                response = TestClient(app).get(
                    "/datasets/dataset-1/preview?limit=100"
                )

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["rows"][0]["sales"], 10)


class GeneratorTests(unittest.TestCase):
    def test_generated_dashboard_is_valid_python(self):
        code = generate_streamlit_code(
            validate_dashboard_schema(make_schema())
        )

        compile(code, "generated_app.py", "exec")
        self.assertIn("from streamlit_elements import", code)
        self.assertIn("dashboard.Grid", code)
        self.assertIn("nivo.", code)
        self.assertIn("'height': 360", code)
        self.assertIn("'color': '#818cf8'", code)
        self.assertIn("calculate_metric", code)
        self.assertIn("render_filters", code)
        self.assertIn("render_metrics", code)

    def test_generates_every_supported_chart_type(self):
        for chart_type in (
            "line_chart",
            "bar_chart",
            "area_chart",
            "scatter_plot",
        ):
            with self.subTest(chart_type=chart_type):
                schema = make_schema()
                schema["views"][0]["type"] = chart_type
                code = generate_streamlit_code(
                    validate_dashboard_schema(schema)
                )

                compile(code, "generated_app.py", "exec")
                self.assertIn(f"'type': '{chart_type}'", code)
                self.assertIn("render_chart", code)

    def test_generates_component_gradient_chart(self):
        schema = make_schema()
        schema["views"][0].update({
            "type": "bar_chart",
            "colorMode": "gradient",
            "palette": ["#fbbf24", "#f97316", "#ef4444"],
        })

        code = generate_streamlit_code(
            validate_dashboard_schema(schema)
        )

        compile(code, "generated_app.py", "exec")
        self.assertNotIn("import altair as alt", code)
        self.assertIn("'colorMode': 'gradient'", code)
        self.assertIn(
            "'palette': ['#fbbf24', '#f97316', '#ef4444']",
            code,
        )
        self.assertIn("interpolate_color", code)
        self.assertIn('colors={"datum": "data.color"}', code)

    def test_freeform_grid_fills_space_below_short_components(self):
        code = generate_streamlit_code(
            validate_dashboard_schema(make_schema())
        )
        tree = ast.parse(code)
        layout_functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"grid_height", "pack_views"}
        ]
        namespace = {
            "GRID_COLUMNS": 12,
            "GRID_ROW_HEIGHT": 22,
            "GRID_GAP": 16,
            "CARD_CHROME_HEIGHT": 70,
        }
        exec(
            compile(
                ast.Module(body=layout_functions, type_ignores=[]),
                "generated_layout.py",
                "exec",
            ),
            namespace,
        )
        items = [
            {"id": "metric", "order": 1, "layout": {"width": 3, "height": 160}},
            {"id": "chart-1", "order": 2, "layout": {"width": 6, "height": 280}},
            {"id": "chart-2", "order": 3, "layout": {"width": 6, "height": 220}},
        ]

        packed = namespace["pack_views"](items)

        self.assertEqual(
            [
                (item["view"]["id"], item["x"], item["y"])
                for item in packed
            ],
            [
                ("metric", 0, 0),
                ("chart-1", 4, 0),
                ("chart-2", 0, namespace["grid_height"](items[1])),
            ],
        )

    def test_generated_dashboard_executes_in_streamlit_bare_mode(self):
        schema = make_schema()
        schema["views"][0].update({
            "type": "bar_chart",
            "colorMode": "gradient",
            "palette": ["#fbbf24", "#f97316", "#ef4444"],
            "sort": "desc",
            "sortBy": "y",
        })
        code = generate_streamlit_code(
            validate_dashboard_schema(schema)
        )

        with tempfile.TemporaryDirectory() as directory:
            project_dir = Path(directory)
            data_dir = project_dir / "data"
            data_dir.mkdir()
            (project_dir / "app.py").write_text(code, encoding="utf-8")
            (data_dir / "sales.csv").write_text(
                "date,region,sales\n2026-01-01,A,10\n2026-01-02,B,20\n",
                encoding="utf-8",
            )
            environment = {
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
            }

            result = subprocess.run(
                [sys.executable, "-B", str(project_dir / "app.py")],
                cwd=project_dir,
                capture_output=True,
                text=True,
                timeout=30,
                env=environment,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)


class RuntimeRendererTests(unittest.TestCase):
    def test_runtime_uses_interactive_elements_grid(self):
        dataframe = pd.DataFrame({
            "region": ["A", "B"],
            "sales": [10, 20],
        })

        with patch.object(
            preview_runtime_render,
            "render_elements_dashboard",
        ) as grid_output, patch.object(
            preview_runtime_render.st,
            "title",
        ), patch.object(
            preview_runtime_render.st,
            "caption",
        ):
            preview_runtime_render.render_runtime_dashboard(
                make_schema(),
                dataframe,
            )

        grid_output.assert_called_once()
        self.assertIs(grid_output.call_args.args[1], dataframe)


class PreviewServiceTests(unittest.TestCase):
    def test_creates_updates_and_deletes_session(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset_path = Path(directory) / "data.csv"
            dataset_path.write_text("region,sales\nA,10\n", encoding="utf-8")
            service = PreviewService(
                ttl_seconds=60,
                public_url="http://preview.test",
            )

            with patch(
                "app.services.preview_service.get_dataset_path",
                return_value=dataset_path,
            ):
                created = service.create_preview(
                    "user-1",
                    make_schema(),
                    "dataset-1",
                )
                updated = service.update_preview(
                    created["sessionId"],
                    "user-1",
                    make_schema(),
                    "dataset-1",
                )

                self.assertEqual(created["revision"], 1)
                self.assertEqual(updated["revision"], 2)
                self.assertIn("revision=2", updated["previewUrl"])
                self.assertEqual(
                    service.get_preview(created["sessionId"])["revision"],
                    2,
                )
                self.assertEqual(
                    service.delete_preview(created["sessionId"], "user-1"),
                    {"deleted": True},
                )


if __name__ == "__main__":
    unittest.main()
