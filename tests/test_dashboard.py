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
from streamlit.testing.v1 import AppTest

from app.api.datasets_routes import router as datasets_router
from app.schemas.dashboard import validate_dashboard_schema
from app.services.generator_service import generate_streamlit_code
from app.services import auth_service, dataset_service
from app.services.preview_service import PreviewService
from app.utils.data_transform import (
    calculate_metric,
    prepare_chart_data,
)
from app.utils.schema_utils import (
    get_dashboard_title,
    python_string_literal,
)
from app.services.renderers import render_core


def make_schema() -> dict:
    return {
        "version": 2,
        "dashboard": {
            "title": "Sales dashboard",
            "grid": {"columns": 12},
        },
        "dataSources": [
            {
                "type": "backend_dataset",
                "datasetId": "dataset-1",
                "name": "sales.csv",
                "fields": ["date", "region", "sales"],
            }
        ],
        "filters": [
            {
                "id": "filter-1",
                "type": "selectbox",
                "datasetId": "dataset-1",
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
                "datasetId": "dataset-1",
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
                "datasetId": "dataset-1",
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
        self.assertEqual(schema["dataSources"][0]["datasetId"], "dataset-1")
        self.assertEqual(schema["views"][0]["datasetId"], "dataset-1")

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

    def test_accepts_compact_filter_height(self):
        schema = make_schema()
        schema["filters"][0]["layout"]["height"] = 60

        validated = validate_dashboard_schema(schema)

        self.assertEqual(validated["filters"][0]["layout"]["height"], 60)

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


class SchemaUtilsTests(unittest.TestCase):
    def test_gets_dashboard_title_and_fallback(self):
        self.assertEqual(get_dashboard_title({"dashboard": {"title": "My Title"}}), "My Title")
        self.assertEqual(get_dashboard_title({}), "Untitled project")

    def test_formats_python_string_literal(self):
        self.assertEqual(python_string_literal("hello"), "'hello'")
        self.assertEqual(python_string_literal(None, "fallback"), "'fallback'")


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

    def test_inspect_and_preview_excel_sheets(self):
        import io
        from fastapi import UploadFile

        with tempfile.TemporaryDirectory() as directory:
            datasets_dir = Path(directory)
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                pd.DataFrame({"a": [1, 2]}).to_excel(writer, sheet_name="SheetA", index=False)
                pd.DataFrame({"b": [3, 4]}).to_excel(writer, sheet_name="SheetB", index=False)
            excel_bytes = excel_buffer.getvalue()

            upload_file = UploadFile(
                filename="test.xlsx",
                file=io.BytesIO(excel_bytes),
            )
            sheets = dataset_service.inspect_excel_sheets(upload_file)
            self.assertEqual(sheets, ["SheetA", "SheetB"])

            with patch.object(dataset_service, "DATASETS_DIR", datasets_dir):
                saved = dataset_service.save_dataset(
                    user_id="user-1",
                    file=upload_file,
                    custom_name="custom_report",
                    sheet_name="SheetB",
                )
                self.assertEqual(saved["name"], "custom_report.xlsx")
                self.assertEqual(saved["sheetName"], "SheetB")
                self.assertEqual(saved["fields"], ["b"])

                preview = dataset_service.get_dataset_preview("user-1", saved["datasetId"])
                self.assertEqual(preview["fields"], ["b"])
                self.assertEqual(preview["rows"][0]["b"], 3)

    def test_save_and_preview_tsv(self):
        import io
        from fastapi import UploadFile

        with tempfile.TemporaryDirectory() as directory:
            datasets_dir = Path(directory)
            tsv_data = "col1\tcol2\n10\t20\n".encode("utf-8")
            upload_file = UploadFile(
                filename="data.tsv",
                file=io.BytesIO(tsv_data),
            )

            with patch.object(dataset_service, "DATASETS_DIR", datasets_dir):
                saved = dataset_service.save_dataset(
                    user_id="user-1",
                    file=upload_file,
                    delimiter="\t",
                )
                self.assertEqual(saved["format"], "tsv")
                self.assertEqual(saved["delimiter"], "\t")

                preview = dataset_service.get_dataset_preview("user-1", saved["datasetId"])
                self.assertEqual(preview["fields"], ["col1", "col2"])
                self.assertEqual(preview["rows"][0]["col1"], 10)


class GeneratorTests(unittest.TestCase):
    def test_generated_dashboard_is_valid_python(self):
        code = generate_streamlit_code(
            validate_dashboard_schema(make_schema())
        )

        compile(code, "generated_app.py", "exec")
        self.assertNotIn("from streamlit_elements import", code)
        self.assertIn("display: grid !important", code)
        self.assertIn("st.vega_lite_chart", code)
        self.assertIn("@st.cache_data(show_spinner=False)", code)
        self.assertIn("'height': 360", code)
        self.assertIn("'color': '#818cf8'", code)
        self.assertIn("calculate_metric", code)
        self.assertIn("render_filter", code)
        self.assertIn("render_metric", code)
        self.assertIn("components_from_schema", code)

    def test_generated_dashboard_with_excel_and_custom_delimiter_is_valid_python(self):
        schema = make_schema()
        schema["dataSources"] = [
            {
                "type": "backend_dataset",
                "datasetId": "ds-excel",
                "name": "report.xlsx",
                "format": "excel",
                "sheetName": "Лист2",
            },
            {
                "type": "backend_dataset",
                "datasetId": "ds-tsv",
                "name": "data.tsv",
                "format": "tsv",
                "delimiter": "\t",
            },
        ]
        code = generate_streamlit_code(validate_dashboard_schema(schema))
        compile(code, "generated_app_excel.py", "exec")
        self.assertIn("pd.read_excel", code)
        self.assertIn("'sheetName': 'Лист2'", code)

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

    def test_generates_text_component(self):
        schema = make_schema()
        schema["views"].append({
            "id": "text-1",
            "type": "text",
            "datasetId": None,
            "order": 3,
            "layout": {"width": 6, "height": 60},
            "title": "",
            "content": "Данные обновляются раз в неделю.",
            "fontSize": 20,
            "fontWeight": "bold",
            "fontStyle": "italic",
            "color": "#38bdf8",
            "textAlign": "center",
        })

        validated_schema = validate_dashboard_schema(schema)
        code = generate_streamlit_code(validated_schema)

        compile(code, "generated_app.py", "exec")
        self.assertEqual(validated_schema["views"][2]["type"], "text")
        self.assertEqual(validated_schema["views"][2]["title"], "")
        self.assertEqual(validated_schema["views"][2]["layout"]["height"], 60)
        self.assertEqual(validated_schema["views"][2]["fontSize"], 20)
        self.assertIn("Данные обновляются раз в неделю.", code)
        self.assertIn("render_text", code)

    def test_rejects_too_small_chart_height(self):
        schema = make_schema()
        schema["views"][0]["layout"]["height"] = 60

        with self.assertRaises(ValidationError):
            validate_dashboard_schema(schema)

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
        self.assertNotIn("streamlit_elements", code)
        self.assertIn("'colorMode': 'gradient'", code)
        self.assertIn(
            "'palette': ['#fbbf24', '#f97316', '#ef4444']",
            code,
        )
        self.assertIn("color_encoding", code)
        self.assertIn('"scale": {"range": palette}', code)

    def test_generated_filter_uses_native_streamlit_widget(self):
        code = generate_streamlit_code(
            validate_dashboard_schema(make_schema())
        )
        tree = ast.parse(code)
        state_key_function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "component_state_key"
        )
        namespace = {}
        exec(
            compile(
                ast.Module(body=[state_key_function], type_ignores=[]),
                "generated_filter.py",
                "exec",
            ),
            namespace,
        )

        self.assertEqual(
            namespace["component_state_key"]({
                "id": "selectbox-f5aa998d-8c1d-4741-9379-26eecebafa4a",
            }),
            "builder_filter_selectbox_f5aa998d_8c1d_4741_9379_26eecebafa4a",
        )
        self.assertIn("st.selectbox(", code)
        self.assertNotIn("onChange=filter_change_handler", code)

    def test_dense_x_axis_uses_evenly_distributed_tick_values(self):
        code = generate_streamlit_code(
            validate_dashboard_schema(make_schema())
        )
        tree = ast.parse(code)
        tick_function = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "axis_tick_values"
        )
        namespace = {}
        exec(
            compile(
                ast.Module(body=[tick_function], type_ignores=[]),
                "generated_ticks.py",
                "exec",
            ),
            namespace,
        )
        values = [
            f"2026-01-{day:02d}"
            for day in range(1, 32)
        ]

        ticks = namespace["axis_tick_values"](values, 6)

        self.assertEqual(len(ticks), 6)
        self.assertEqual(ticks[0], "2026-01-01")
        self.assertEqual(ticks[-1], "2026-01-31")

    def test_scatter_uses_fast_native_gradient_scale(self):
        schema = make_schema()
        schema["views"][0].update({
            "type": "scatter_plot",
            "colorMode": "gradient",
        })

        code = generate_streamlit_code(validate_dashboard_schema(schema))

        self.assertIn('"type": "point"', code)
        self.assertIn("chart_point_limit", code)
        self.assertIn("downsample_frame", code)
        self.assertIn('"scale": {"range": palette}', code)
        self.assertIn('"size": 420', code)
        self.assertIn('"nearest": True', code)
        self.assertIn('"on": "pointerover"', code)

    def test_line_and_area_charts_use_nearest_hover_guide(self):
        code = generate_streamlit_code(
            validate_dashboard_schema(make_schema())
        )

        self.assertIn('chart_type in {"line_chart", "area_chart"}', code)
        self.assertIn('"type": "rule"', code)
        self.assertIn('"encodings": ["x"]', code)
        self.assertIn('"clear": "pointerout"', code)
        self.assertIn('{"filter": {"param": "hover", "empty": False}}', code)

    def test_freeform_grid_preserves_canvas_positions(self):
        code = generate_streamlit_code(
            validate_dashboard_schema(make_schema())
        )
        tree = ast.parse(code)
        layout_functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in {"grid_height", "pack_components"}
        ]
        namespace = {
            "GRID_COLUMNS": 12,
            "GRID_ROW_HEIGHT": 20,
            "GRID_GAP": 16,
            "CARD_CHROME_HEIGHT": 96,
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
            {"id": "metric", "order": 1, "layout": {"x": 1, "y": 2, "width": 3, "height": 160}},
            {"id": "chart-1", "order": 2, "layout": {"x": 4, "y": 2, "width": 6, "height": 280}},
            {"id": "chart-2", "order": 3, "layout": {"width": 6, "height": 220}},
        ]

        packed = namespace["pack_components"](items)

        self.assertEqual(
            [
                (item["component"]["id"], item["x"], item["y"])
                for item in packed
            ],
            [
                ("metric", 1, 2),
                ("chart-1", 4, 2),
                ("chart-2", 0, 13),
            ],
        )

    def test_generated_dashboard_keeps_filters_in_canvas_rows(self):
        schema = make_schema()
        schema["filters"][0]["layout"].update({"x": 0, "y": 0})
        schema["views"][0]["layout"].update({"x": 4, "y": 0})
        schema["views"][1]["layout"].update({"x": 0, "y": 5})

        code = generate_streamlit_code(validate_dashboard_schema(schema))

        self.assertIn("placements = pack_components(components_from_schema(schema))", code)
        self.assertIn("dashboard_grid_style(placements)", code)
        self.assertIn('with st.container(key="dashboard_grid"):', code)
        self.assertIn('grid_pixel_height(item["h"])', code)
        self.assertIn("render_component(", code)
        self.assertIn('[*schema.get("filters", []), *schema.get("views", [])]', code)

    def test_staggered_canvas_uses_exact_css_grid_coordinates(self):
        code = generate_streamlit_code(
            validate_dashboard_schema(make_schema())
        )
        tree = ast.parse(code)
        names = {
            "component_state_key",
            "grid_height",
            "pack_components",
            "grid_pixel_height",
            "card_container_key",
            "dashboard_grid_style",
        }
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names
        ]
        namespace = {
            "GRID_COLUMNS": 12,
            "GRID_ROW_HEIGHT": 20,
            "GRID_GAP": 16,
            "CARD_CHROME_HEIGHT": 96,
        }
        exec(
            compile(
                ast.Module(body=functions, type_ignores=[]),
                "generated_css_grid.py",
                "exec",
            ),
            namespace,
        )
        components = [
            {"id": "filter", "order": 1, "layout": {"x": 0, "y": 0, "width": 3, "height": 140}},
            {"id": "metric", "order": 2, "layout": {"x": 3, "y": 0, "width": 3, "height": 140}},
            {"id": "right-top", "order": 3, "layout": {"x": 6, "y": 0, "width": 6, "height": 392}},
            {"id": "left-middle", "order": 4, "layout": {"x": 0, "y": 7, "width": 6, "height": 284}},
            {"id": "right-bottom", "order": 5, "layout": {"x": 6, "y": 14, "width": 6, "height": 500}},
            {"id": "left-bottom", "order": 6, "layout": {"x": 0, "y": 18, "width": 6, "height": 356}},
        ]

        placements = namespace["pack_components"](components)
        style = namespace["dashboard_grid_style"](placements)

        self.assertEqual(
            [(item["x"], item["y"], item["w"], item["h"]) for item in placements],
            [
                (0, 0, 3, 7),
                (3, 0, 3, 7),
                (6, 0, 6, 14),
                (0, 7, 6, 11),
                (6, 14, 6, 17),
                (0, 18, 6, 13),
            ],
        )
        self.assertIn("grid-column: 7 / span 6;", style)
        self.assertIn("grid-row: 15 / span 17;", style)
        for component in components:
            safe_id = component["id"].replace("-", "_")
            self.assertIn(f"st-key-card_builder_filter_{safe_id}", style)

    def test_css_grid_supports_non_sliceable_canvas_layouts(self):
        code = generate_streamlit_code(validate_dashboard_schema(make_schema()))
        tree = ast.parse(code)
        names = {
            "component_state_key",
            "card_container_key",
            "dashboard_grid_style",
        }
        functions = [
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in names
        ]
        namespace = {
            "GRID_COLUMNS": 12,
            "GRID_ROW_HEIGHT": 20,
            "GRID_GAP": 16,
        }
        exec(
            compile(
                ast.Module(body=functions, type_ignores=[]),
                "generated_irregular_grid.py",
                "exec",
            ),
            namespace,
        )
        placements = [
            {"x": 0, "y": 0, "w": 8, "h": 6, "component": {"id": "top-left"}},
            {"x": 8, "y": 0, "w": 4, "h": 10, "component": {"id": "top-right"}},
            {"x": 0, "y": 6, "w": 4, "h": 8, "component": {"id": "bottom-left"}},
            {"x": 4, "y": 10, "w": 8, "h": 4, "component": {"id": "bottom-right"}},
        ]

        style = namespace["dashboard_grid_style"](placements)

        self.assertEqual(style.count("grid-column:"), len(placements))
        self.assertEqual(style.count("grid-row:"), len(placements))
        self.assertIn("grid-column: 5 / span 8;", style)
        self.assertIn("grid-row: 11 / span 4;", style)

    def test_generated_native_filter_changes_selected_value(self):
        code = generate_streamlit_code(
            validate_dashboard_schema(make_schema())
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

            app = AppTest.from_file(project_dir / "app.py", default_timeout=20)
            app.run()
            self.assertEqual(len(app.selectbox), 1)
            app.selectbox[0].select("A").run()

        self.assertEqual(app.selectbox[0].value, "A")
        self.assertEqual(len(app.exception), 0)

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
    def test_metric_renderer_centers_value_in_compact_card(self):
        component = {
            "title": "Продажи",
            "field": "sales",
            "aggregation": "sum",
            "layout": {"height": 80},
        }
        dataframe = pd.DataFrame({"sales": [10, 20]})

        with patch.object(render_core.st, "markdown") as markdown_mock:
            render_core.render_metric(component, dataframe)

        rendered_html = markdown_mock.call_args.args[0]
        self.assertIn("justify-content:center", rendered_html)
        self.assertIn("min-height:32px", rendered_html)
        self.assertIn(">30<", rendered_html)
        self.assertNotIn("sum · sales", rendered_html)

    def test_compact_components_use_shorter_grid_rows(self):
        metric = {"type": "metric", "layout": {"height": 140}}
        text = {"type": "text", "layout": {"height": 60}}
        selectbox = {"type": "selectbox", "layout": {"height": 80}}

        self.assertEqual(render_core.grid_height(metric), 5)
        self.assertEqual(render_core.grid_height(text), 3)
        self.assertEqual(render_core.grid_height(selectbox), 3)

    def test_renderer_keeps_editor_grid_coordinates(self):
        components = [
            {"type": "metric", "order": 1, "layout": {"x": 0, "y": 0, "width": 3, "height": 140}},
            {"type": "bar_chart", "order": 2, "layout": {"x": 0, "y": 7, "width": 3, "height": 248}},
            {"type": "line_chart", "order": 3, "layout": {"x": 3, "y": 0, "width": 6, "height": 320}},
            {"type": "text", "order": 4, "layout": {"x": 3, "y": 12, "width": 6, "height": 60}},
        ]

        metric, bar, line, text = render_core.pack_components(components)

        self.assertEqual((metric["y"], metric["h"]), (0, 5))
        self.assertEqual((bar["y"], bar["h"]), (7, 10))
        self.assertEqual((line["y"], line["h"]), (0, 12))
        self.assertEqual((text["y"], text["h"]), (12, 3))

    def test_text_renderer_applies_style_and_escapes_html(self):
        component = {
            "title": "Комментарий",
            "content": "<script>alert('x')</script>\nВторая строка",
            "fontSize": 20,
            "fontWeight": "bold",
            "fontStyle": "italic",
            "color": "#38bdf8",
            "textAlign": "center",
        }

        with patch.object(render_core.st, "markdown") as markdown_mock:
            render_core.render_text(component)

        rendered_html = markdown_mock.call_args_list[1].args[0]
        self.assertIn("font-size: 20px", rendered_html)
        self.assertIn("font-weight: bold", rendered_html)
        self.assertIn("text-align: center", rendered_html)
        self.assertIn("&lt;script&gt;", rendered_html)
        self.assertNotIn("<script>", rendered_html)

    def test_runtime_renders_native_dashboard(self):
        dataframe = pd.DataFrame({
            "region": ["A", "B"],
            "sales": [10, 20],
        })
        schema = make_schema()
        datasets = {"dataset-1": dataframe}
        with patch.object(render_core.st, "markdown") as markdown_mock, \
                patch.object(render_core.st, "container") as container_mock:
            render_core.render_dashboard(schema, datasets)
        markdown_mock.assert_called()
        container_mock.assert_called()


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
                )
                updated = service.update_preview(
                    created["sessionId"],
                    "user-1",
                    make_schema(),
                )

                self.assertEqual(created["revision"], 1)
                self.assertEqual(updated["revision"], 2)
                self.assertIn("revision=2", updated["previewUrl"])
                session = service.get_preview(created["sessionId"])
                self.assertEqual(session["revision"], 2)
                self.assertIn("dataset-1", session["datasetsPaths"])
                self.assertEqual(
                    service.delete_preview(created["sessionId"], "user-1"),
                    {"deleted": True},
                )

    def test_creates_preview_with_multiple_datasets(self):
        with tempfile.TemporaryDirectory() as directory:
            path_a = Path(directory) / "sales.csv"
            path_b = Path(directory) / "targets.csv"
            path_a.write_text("region,sales\nA,10\n", encoding="utf-8")
            path_b.write_text("region,target\nA,15\n", encoding="utf-8")

            schema = make_schema()
            schema["dataSources"] = [
                {"type": "backend_dataset", "datasetId": "ds-a", "name": "sales.csv"},
                {"type": "backend_dataset", "datasetId": "ds-b", "name": "targets.csv"},
            ]

            service = PreviewService(ttl_seconds=60)

            def fake_get_path(user_id, ds_id):
                return path_a if ds_id == "ds-a" else path_b

            with patch(
                "app.services.preview_service.get_dataset_path",
                side_effect=fake_get_path,
            ):
                created = service.create_preview("user-1", schema)
                session = service.get_preview(created["sessionId"])

                self.assertEqual(len(session["datasetsPaths"]), 2)
                self.assertIn("ds-a", session["datasetsPaths"])
                self.assertIn("ds-b", session["datasetsPaths"])


if __name__ == "__main__":
    unittest.main()
