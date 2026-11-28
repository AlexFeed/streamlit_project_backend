import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from pydantic import ValidationError
from streamlit.testing.v1 import AppTest

from app.schemas.dashboard import validate_dashboard_schema
from app.services.generator_service import generate_streamlit_code
from app.services.renderers import render_core
from app.utils.schema_utils import (
    get_dashboard_title,
    python_string_literal,
)


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


# --- Dashboard Schema v2 validation ---


class DashboardSchemaTests(unittest.TestCase):
    def test_validates_schema_v2(self):
        schema = validate_dashboard_schema(make_schema())

        self.assertEqual(schema["version"], 2)
        self.assertEqual(schema["views"][0]["layout"]["width"], 8)
        self.assertEqual(schema["views"][0]["layout"]["height"], 360)
        self.assertEqual(schema["views"][0]["color"], "#818cf8")
        self.assertEqual(schema["dataSources"][0]["datasetId"], "dataset-1")
        self.assertEqual(schema["views"][0]["datasetId"], "dataset-1")
        self.assertEqual(schema["pages"][0]["id"], "page-main")
        self.assertEqual(schema["views"][0]["pageId"], "page-main")

    def test_validates_multiple_pages(self):
        schema = make_schema()
        schema["pages"] = [
            {"id": "page-main", "title": "Главная", "order": 1},
            {"id": "page-details", "title": "Детали", "order": 2},
        ]
        schema["views"][0]["pageId"] = "page-details"

        validated = validate_dashboard_schema(schema)

        self.assertEqual(len(validated["pages"]), 2)
        self.assertEqual(validated["views"][0]["pageId"], "page-details")

    def test_rejects_component_with_unknown_page(self):
        schema = make_schema()
        schema["views"][0]["pageId"] = "missing-page"

        with self.assertRaises(ValueError):
            validate_dashboard_schema(schema)

    def test_validates_filter_variants_navigation_and_table(self):
        schema = make_schema()
        schema["pages"] = [
            {"id": "page-main", "title": "Главная", "order": 1},
            {"id": "page-details", "title": "Детали", "order": 2},
        ]
        schema["filters"][0]["widget"] = "radio"
        schema["views"].extend([
            {
                "id": "table-1",
                "type": "table",
                "pageId": "page-main",
                "datasetId": "dataset-1",
                "order": 4,
                "layout": {"width": 8, "height": 320},
                "title": "Продажи",
                "columns": ["region", "sales"],
                "rowLimit": 25,
                "hideIndex": True,
            },
            {
                "id": "link-1",
                "type": "page_link",
                "pageId": "page-main",
                "datasetId": None,
                "order": 5,
                "layout": {"width": 3, "height": 60},
                "title": "Подробнее",
                "targetPageId": "page-details",
                "displayStyle": "button",
            },
        ])

        validated = validate_dashboard_schema(schema)

        self.assertEqual(validated["filters"][0]["widget"], "radio")
        self.assertEqual(validated["views"][-2]["columns"], ["region", "sales"])
        self.assertEqual(validated["views"][-1]["targetPageId"], "page-details")

    def test_validates_pivot_table_and_page_button_color(self):
        schema = make_schema()
        schema["pages"] = [
            {"id": "page-main", "title": "Main", "order": 1},
            {"id": "page-details", "title": "Details", "order": 2},
        ]
        schema["views"].extend([
            {
                "id": "pivot-1", "type": "table", "pageId": "page-main",
                "datasetId": "dataset-1", "order": 4,
                "layout": {"width": 6, "height": 320},
                "tableMode": "pivot", "rowMode": "all",
                "pivotIndex": "region", "pivotValue": "sales",
                "pivotAggregation": "mean",
            },
            {
                "id": "link-1", "type": "page_link", "pageId": "page-main",
                "datasetId": None, "order": 5,
                "layout": {"width": 2, "height": 60},
                "targetPageId": "page-details", "buttonColor": "#2563eb",
                "elementFontSize": 12,
            },
        ])

        validated = validate_dashboard_schema(schema)

        self.assertEqual(validated["views"][-2]["pivotAggregation"], "mean")
        self.assertEqual(validated["views"][-2]["rowMode"], "all")
        self.assertEqual(validated["views"][-1]["buttonColor"], "#2563eb")
        self.assertEqual(validated["views"][-1]["elementFontSize"], 12)

    def test_rejects_navigation_to_unknown_target_page(self):
        schema = make_schema()
        schema["views"].append({
            "id": "link-1",
            "type": "page_link",
            "pageId": "page-main",
            "order": 4,
            "layout": {"width": 3, "height": 60},
            "title": "Подробнее",
            "targetPageId": "missing-page",
            "displayStyle": "link",
        })

        with self.assertRaises(ValueError):
            validate_dashboard_schema(schema)

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

    def test_rejects_too_small_chart_height(self):
        schema = make_schema()
        schema["views"][0]["layout"]["height"] = 60

        with self.assertRaises(ValidationError):
            validate_dashboard_schema(schema)

    def test_rejects_layout_exceeding_grid_columns(self):
        schema = make_schema()
        schema["views"][0]["layout"].update({"x": 8, "width": 5})

        with self.assertRaises(ValidationError):
            validate_dashboard_schema(schema)

    def test_validates_data_control_filter_variants(self):
        for control_type in ("range", "date", "toggle"):
            with self.subTest(control_type=control_type):
                schema = make_schema()
                schema["filters"].append({
                    "id": f"control-{control_type}",
                    "type": "data_control",
                    "datasetId": "dataset-1",
                    "order": 10,
                    "layout": {"width": 4, "height": 80},
                    "field": "sales",
                    "controlType": control_type,
                })

                validated = validate_dashboard_schema(schema)
                self.assertEqual(validated["filters"][-1]["controlType"], control_type)

    def test_rejects_progress_with_non_increasing_range(self):
        schema = make_schema()
        schema["views"].append({
            "id": "progress-1",
            "type": "progress",
            "datasetId": "dataset-1",
            "order": 4,
            "layout": {"width": 4, "height": 80},
            "field": "sales",
            "minimum": 50,
            "maximum": 50,
        })

        with self.assertRaises(ValidationError):
            validate_dashboard_schema(schema)

    def test_rejects_pivot_table_without_required_fields(self):
        schema = make_schema()
        schema["views"].append({
            "id": "pivot-invalid",
            "type": "table",
            "datasetId": "dataset-1",
            "order": 4,
            "layout": {"width": 6, "height": 240},
            "tableMode": "pivot",
            "pivotIndex": "region",
            "pivotValue": "",
        })

        with self.assertRaises(ValidationError):
            validate_dashboard_schema(schema)

    def test_rejects_nested_groups_and_cross_page_parent(self):
        # Nested layout_group inside another layout_group is forbidden.
        nested_schema = make_schema()
        nested_schema["views"].extend([
            {
                "id": "group-outer",
                "type": "layout_group",
                "order": 4,
                "layout": {"width": 6, "height": 200},
            },
            {
                "id": "group-inner",
                "type": "layout_group",
                "parentId": "group-outer",
                "order": 5,
                "layout": {"width": 6, "height": 120},
            },
        ])
        with self.assertRaises(ValidationError):
            validate_dashboard_schema(nested_schema)

        # Child component cannot reference a parent group on a different page.
        cross_page_schema = make_schema()
        cross_page_schema["pages"] = [
            {"id": "page-main", "title": "Main", "order": 1},
            {"id": "page-other", "title": "Other", "order": 2},
        ]
        cross_page_schema["views"].append({
            "id": "group-other",
            "type": "layout_group",
            "pageId": "page-other",
            "order": 4,
            "layout": {"width": 6, "height": 200},
        })
        cross_page_schema["views"][1]["parentId"] = "group-other"

        with self.assertRaises(ValidationError):
            validate_dashboard_schema(cross_page_schema)

    def test_rejects_unknown_extra_fields_on_components(self):
        schema = make_schema()
        schema["views"][0]["unexpectedProp"] = True

        with self.assertRaises(ValidationError):
            validate_dashboard_schema(schema)

    def test_rejects_duplicate_page_ids(self):
        schema = make_schema()
        schema["pages"] = [
            {"id": "page-main", "title": "First", "order": 1},
            {"id": "page-main", "title": "Duplicate", "order": 2},
        ]

        with self.assertRaises(ValidationError):
            validate_dashboard_schema(schema)


# --- Schema utility helpers ---


class SchemaUtilsTests(unittest.TestCase):
    def test_gets_dashboard_title_and_fallback(self):
        self.assertEqual(get_dashboard_title({"dashboard": {"title": "My Title"}}), "My Title")
        self.assertEqual(get_dashboard_title({}), "Untitled project")

    def test_formats_python_string_literal(self):
        self.assertEqual(python_string_literal("hello"), "'hello'")
        self.assertEqual(python_string_literal(None, "fallback"), "'fallback'")


# --- Standalone Streamlit code generation and AppTest execution ---


class GeneratorTests(unittest.TestCase):
    def test_generated_dashboard_is_valid_python(self):
        code = generate_streamlit_code(
            validate_dashboard_schema(make_schema())
        )

        compile(code, "generated_app.py", "exec")
        self.assertIn("@st.cache_data(show_spinner=False)", code)
        self.assertIn("'height': 360", code)
        self.assertIn("'color': '#818cf8'", code)
        self.assertIn("render_multipage_dashboard(DASHBOARD_SCHEMA, datasets)", code)

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
        self.assertIn("'sheetName': 'Лист2'", code)
        self.assertIn("'delimiter': '\\t'", code)

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
            self.assertEqual(app.metric[0].value, "30")
            app.selectbox[0].select("A").run()

        self.assertEqual(app.selectbox[0].value, "A")
        self.assertEqual(app.metric[0].value, "10")
        self.assertEqual(len(app.exception), 0)

    def test_generated_dashboard_loads_excel_sheet_and_cp1251_csv_in_apptest(self):
        schema = {
            "version": 2,
            "dashboard": {"title": "Multi-format dashboard", "grid": {"columns": 12}},
            "dataSources": [
                {
                    "type": "backend_dataset",
                    "datasetId": "ds-excel",
                    "name": "report.xlsx",
                    "format": "excel",
                    "sheetName": "TargetSheet",
                },
                {
                    "type": "backend_dataset",
                    "datasetId": "ds-cp1251",
                    "name": "sales_ru.csv",
                    "format": "csv",
                    "delimiter": ";",
                    "encoding": "cp1251",
                },
            ],
            "filters": [],
            "views": [
                {
                    "id": "metric-excel",
                    "type": "metric",
                    "datasetId": "ds-excel",
                    "order": 1,
                    "layout": {"width": 6, "height": 120},
                    "title": "Excel total",
                    "field": "amount",
                    "aggregation": "sum",
                },
                {
                    "id": "metric-csv",
                    "type": "metric",
                    "datasetId": "ds-cp1251",
                    "order": 2,
                    "layout": {"width": 6, "height": 120},
                    "title": "CSV total",
                    "field": "продажи",
                    "aggregation": "sum",
                },
            ],
        }
        code = generate_streamlit_code(validate_dashboard_schema(schema))

        with tempfile.TemporaryDirectory() as directory:
            project_dir = Path(directory)
            data_dir = project_dir / "data"
            data_dir.mkdir()
            (project_dir / "app.py").write_text(code, encoding="utf-8")

            with pd.ExcelWriter(data_dir / "report.xlsx", engine="openpyxl") as writer:
                pd.DataFrame({"amount": [1]}).to_excel(writer, sheet_name="Ignored", index=False)
                pd.DataFrame({"amount": [15, 25]}).to_excel(
                    writer,
                    sheet_name="TargetSheet",
                    index=False,
                )

            (data_dir / "sales_ru.csv").write_bytes(
                "город;продажи\nМосква;120\nКазань;80\n".encode("cp1251")
            )

            app = AppTest.from_file(project_dir / "app.py", default_timeout=20)
            app.run()

        self.assertEqual(len(app.exception), 0)
        self.assertEqual([m.value for m in app.metric], ["40", "200"])

    def test_generated_multipage_dashboard_starts(self):
        schema = make_schema()
        schema["pages"] = [
            {"id": "page-main", "title": "Главная", "order": 1},
            {"id": "page-details", "title": "Детали", "order": 2},
        ]
        schema["views"][0]["pageId"] = "page-details"
        schema["views"].extend([
            {
                "id": "table-1",
                "type": "table",
                "pageId": "page-main",
                "datasetId": "dataset-1",
                "order": 4,
                "layout": {"width": 8, "height": 240},
                "title": "Продажи",
                "columns": ["region", "sales"],
                "rowLimit": 10,
                "hideIndex": True,
            },
            {
                "id": "link-1",
                "type": "page_link",
                "pageId": "page-main",
                "order": 5,
                "layout": {"width": 3, "height": 60},
                "title": "Подробнее",
                "targetPageId": "page-details",
                "displayStyle": "link",
            },
        ])
        code = generate_streamlit_code(validate_dashboard_schema(schema))

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

        self.assertEqual(len(app.exception), 0)
        self.assertEqual(len(app.dataframe), 1)
        self.assertEqual(len(app.get('page_link')), 1)

    def test_generated_tab_group_starts_with_multiple_children(self):
        schema = make_schema()
        schema["views"].append({
            "id": "tabs-1",
            "type": "tab_group",
            "pageId": "page-main",
            "order": 10,
            "layout": {"width": 12, "height": 360},
            "tabs": [
                {"id": "tab-1", "label": "Обзор продаж"},
                {"id": "tab-2", "label": "Детали"},
            ],
        })
        schema["views"][0].update({"parentId": "tabs-1", "tabId": "tab-1", "layout": {"width": 4, "height": 220}})
        schema["views"][1].update({"parentId": "tabs-1", "tabId": "tab-1", "layout": {"width": 4, "height": 100}})
        code = generate_streamlit_code(validate_dashboard_schema(schema))

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

    @staticmethod
    def _make_realistic_showcase_schema() -> dict:
        dataset_id = "0712c9f9-01bb-4bfc-9aed-f8bed18eb4b2"
        page_two_id = "page-303d9150-38b3-4178-bbdf-ccc6c5161e18"
        group_id = "layout_group-b0133c4f-a382-4bcf-bccd-46f7907c7909"
        return {
            "version": 2,
            "dashboard": {"title": "Анализ продаж ", "grid": {"columns": 12}},
            "pages": [
                {"id": "page-main", "title": "Главная", "order": 1},
                {"id": page_two_id, "title": "Страница 2", "order": 2},
            ],
            "dataSources": [
                {
                    "type": "backend_dataset",
                    "datasetId": dataset_id,
                    "name": "dashboard_showcase.csv",
                    "format": "csv",
                    "delimiter": None,
                    "encoding": None,
                    "sheetName": None,
                    "fields": [
                        "order_id", "date", "month", "region", "category",
                        "product", "channel", "customer_segment", "quantity",
                        "unit_price", "discount", "revenue", "cost", "profit",
                        "satisfaction_score",
                    ],
                }
            ],
            "filters": [
                {
                    "id": "selectbox-13fcd432-94f5-4b5d-a5c5-d499f37c005f",
                    "type": "selectbox",
                    "pageId": "page-main",
                    "parentId": None,
                    "tabId": None,
                    "surface": "card",
                    "showBorder": True,
                    "showBackground": True,
                    "contentAlignment": "left",
                    "verticalAlignment": "center",
                    "padding": 8,
                    "spacing": 0,
                    "contentWidth": "stretch",
                    "heightMode": "fixed",
                    "elementFontSize": "auto",
                    "elementTextColor": "#d4d4d8",
                    "elementFontWeight": "normal",
                    "elementFontStyle": "normal",
                    "datasetId": dataset_id,
                    "order": 3,
                    "layout": {"x": 0, "y": 0, "width": 3, "height": 160},
                    "title": "Фильтр",
                    "field": "region",
                    "scope": "global",
                    "widget": "selectbox",
                },
                {
                    "id": "selectbox-c04512f3-d993-4a74-b7fc-a206d1807553",
                    "type": "selectbox",
                    "pageId": "page-main",
                    "parentId": group_id,
                    "tabId": None,
                    "surface": "card",
                    "showBorder": True,
                    "showBackground": True,
                    "contentAlignment": "left",
                    "verticalAlignment": "center",
                    "padding": 8,
                    "spacing": 0,
                    "contentWidth": "stretch",
                    "heightMode": "auto",
                    "elementFontSize": "auto",
                    "elementTextColor": "#d4d4d8",
                    "elementFontWeight": "normal",
                    "elementFontStyle": "normal",
                    "datasetId": dataset_id,
                    "order": 10,
                    "layout": {"x": 0, "y": 0, "width": 2, "height": 80},
                    "title": "",
                    "field": "category",
                    "scope": "global",
                    "widget": "selectbox",
                },
                {
                    "id": "data_control-66b565d3-cc17-45bd-95f8-be4f2d70ab5f",
                    "type": "data_control",
                    "pageId": "page-main",
                    "parentId": None,
                    "tabId": None,
                    "surface": "card",
                    "showBorder": True,
                    "showBackground": True,
                    "contentAlignment": "left",
                    "verticalAlignment": "center",
                    "padding": 8,
                    "spacing": 0,
                    "contentWidth": "stretch",
                    "heightMode": "fixed",
                    "elementFontSize": "auto",
                    "elementTextColor": "#d4d4d8",
                    "elementFontWeight": "normal",
                    "elementFontStyle": "normal",
                    "datasetId": dataset_id,
                    "order": 12,
                    "layout": {"x": 1, "y": 59, "width": 4, "height": 160},
                    "title": "",
                    "field": "date",
                    "scope": "global",
                    "controlType": "date",
                },
            ],
            "views": [
                {
                    "id": "table-a1ecf907-e0dd-4601-bc05-5e617242b6b7",
                    "type": "table",
                    "pageId": page_two_id,
                    "parentId": None,
                    "tabId": None,
                    "surface": "card",
                    "showBorder": True,
                    "showBackground": True,
                    "contentAlignment": "left",
                    "verticalAlignment": "top",
                    "padding": 12,
                    "spacing": 0,
                    "contentWidth": "stretch",
                    "heightMode": "fixed",
                    "elementFontSize": "auto",
                    "elementTextColor": "#d4d4d8",
                    "elementFontWeight": "normal",
                    "elementFontStyle": "normal",
                    "datasetId": dataset_id,
                    "order": 1,
                    "layout": {"x": 0, "y": 0, "width": 12, "height": 456},
                    "title": "",
                    "columns": [],
                    "tableMode": "data",
                    "rowMode": "limit",
                    "rowLimit": 1150,
                    "hideIndex": True,
                    "pivotIndex": "",
                    "pivotValue": "",
                    "pivotAggregation": "sum",
                },
                {
                    "id": "page_link-f9e7b50a-47d5-4a77-83bb-5700c4080ea0",
                    "type": "page_link",
                    "pageId": page_two_id,
                    "parentId": None,
                    "tabId": None,
                    "surface": "card",
                    "showBorder": True,
                    "showBackground": False,
                    "contentAlignment": "left",
                    "verticalAlignment": "top",
                    "padding": 0,
                    "spacing": 0,
                    "contentWidth": "stretch",
                    "heightMode": "fixed",
                    "elementFontSize": "auto",
                    "elementTextColor": "#d4d4d8",
                    "elementFontWeight": "normal",
                    "elementFontStyle": "normal",
                    "datasetId": None,
                    "order": 2,
                    "layout": {"x": 1, "y": 20, "width": 3, "height": 76},
                    "title": "Открыть страницу",
                    "targetPageId": "page-main",
                    "displayStyle": "button",
                    "buttonColor": "#f47721",
                },
                {
                    "id": "metric-0927275a-8457-4335-880b-fdf0e62abd55",
                    "type": "metric",
                    "pageId": "page-main",
                    "parentId": None,
                    "tabId": None,
                    "surface": "card",
                    "showBorder": True,
                    "showBackground": True,
                    "contentAlignment": "center",
                    "verticalAlignment": "center",
                    "padding": 8,
                    "spacing": 0,
                    "contentWidth": "stretch",
                    "heightMode": "fixed",
                    "elementFontSize": "auto",
                    "elementTextColor": "#d4d4d8",
                    "elementFontWeight": "normal",
                    "elementFontStyle": "normal",
                    "datasetId": dataset_id,
                    "order": 4,
                    "layout": {"x": 8, "y": 0, "width": 4, "height": 160},
                    "title": "Метрика",
                    "description": "Средний чек",
                    "field": "revenue",
                    "aggregation": "mean",
                },
                {
                    "id": "bar_chart-feb0f2a2-9918-489d-9b34-128a7bec54e2",
                    "type": "bar_chart",
                    "pageId": "page-main",
                    "parentId": None,
                    "tabId": None,
                    "surface": "card",
                    "showBorder": True,
                    "showBackground": True,
                    "contentAlignment": "left",
                    "verticalAlignment": "top",
                    "padding": 12,
                    "spacing": 0,
                    "contentWidth": "stretch",
                    "heightMode": "fixed",
                    "elementFontSize": "auto",
                    "elementTextColor": "#d4d4d8",
                    "elementFontWeight": "normal",
                    "elementFontStyle": "normal",
                    "datasetId": dataset_id,
                    "order": 5,
                    "layout": {"x": 0, "y": 6, "width": 6, "height": 344},
                    "title": "ТОП Категорий",
                    "x": "category",
                    "y": "revenue",
                    "aggregation": "sum",
                    "sort": "asc",
                    "sortBy": "y",
                    "color": "#7656c8",
                    "colorMode": "gradient",
                    "palette": ["#277c70", "#2f927a", "#398b67", "#829c3d"],
                    "axisLabelFontSize": 11,
                    "axisLabelColor": "#94a3b8",
                    "axisTitleFontSize": 12,
                    "axisTitleColor": "#94a3b8",
                },
                {
                    "id": "line_chart-e8239d41-5dc3-407a-a790-7b8bead14cd5",
                    "type": "line_chart",
                    "pageId": "page-main",
                    "parentId": None,
                    "tabId": None,
                    "surface": "card",
                    "showBorder": True,
                    "showBackground": True,
                    "contentAlignment": "left",
                    "verticalAlignment": "top",
                    "padding": 12,
                    "spacing": 0,
                    "contentWidth": "stretch",
                    "heightMode": "fixed",
                    "elementFontSize": "auto",
                    "elementTextColor": "#d4d4d8",
                    "elementFontWeight": "normal",
                    "elementFontStyle": "normal",
                    "datasetId": dataset_id,
                    "order": 6,
                    "layout": {"x": 6, "y": 6, "width": 6, "height": 344},
                    "title": "Прибыль по месяцам",
                    "x": "month",
                    "y": "revenue",
                    "aggregation": "sum",
                    "sort": "asc",
                    "sortBy": "x",
                    "color": "#f59e0b",
                    "colorMode": "solid",
                    "palette": ["#3478c8", "#4e78c7", "#7567c9", "#9b62b5"],
                    "axisLabelFontSize": 11,
                    "axisLabelColor": "#94a3b8",
                    "axisTitleFontSize": 12,
                    "axisTitleColor": "#94a3b8",
                },
                {
                    "id": "area_chart-e525583c-1008-422c-b36d-b675391b2fb6",
                    "type": "area_chart",
                    "pageId": "page-main",
                    "parentId": None,
                    "tabId": None,
                    "surface": "card",
                    "showBorder": True,
                    "showBackground": True,
                    "contentAlignment": "left",
                    "verticalAlignment": "top",
                    "padding": 12,
                    "spacing": 0,
                    "contentWidth": "stretch",
                    "heightMode": "fixed",
                    "elementFontSize": "auto",
                    "elementTextColor": "#d4d4d8",
                    "elementFontWeight": "normal",
                    "elementFontStyle": "normal",
                    "datasetId": dataset_id,
                    "order": 7,
                    "layout": {"x": 0, "y": 23, "width": 6, "height": 344},
                    "title": "Динамика чистой прибыли",
                    "x": "month",
                    "y": "profit",
                    "aggregation": "mean",
                    "sort": "asc",
                    "sortBy": "x",
                    "color": "#818cf8",
                    "colorMode": "solid",
                    "palette": ["#c94f8a", "#b94f9a", "#9859b8", "#7656c8"],
                    "axisLabelFontSize": 11,
                    "axisLabelColor": "#94a3b8",
                    "axisTitleFontSize": 12,
                    "axisTitleColor": "#94a3b8",
                },
                {
                    "id": "scatter_plot-6736b01d-44c8-44db-85a7-cbddcb981ee0",
                    "type": "scatter_plot",
                    "pageId": "page-main",
                    "parentId": None,
                    "tabId": None,
                    "surface": "card",
                    "showBorder": True,
                    "showBackground": True,
                    "contentAlignment": "left",
                    "verticalAlignment": "top",
                    "padding": 12,
                    "spacing": 0,
                    "contentWidth": "stretch",
                    "heightMode": "fixed",
                    "elementFontSize": "auto",
                    "elementTextColor": "#d4d4d8",
                    "elementFontWeight": "normal",
                    "elementFontStyle": "normal",
                    "datasetId": dataset_id,
                    "order": 8,
                    "layout": {"x": 6, "y": 23, "width": 6, "height": 344},
                    "title": "Корреляция выручки и прибыли",
                    "x": "revenue",
                    "y": "profit",
                    "aggregation": "none",
                    "sort": "none",
                    "sortBy": "x",
                    "color": "#38bdf8",
                    "colorMode": "gradient",
                    "palette": ["#829c3d", "#398b67", "#2f927a", "#277c70"],
                    "axisLabelFontSize": 11,
                    "axisLabelColor": "#94a3b8",
                    "axisTitleFontSize": 12,
                    "axisTitleColor": "#94a3b8",
                },
                {
                    "id": group_id,
                    "type": "layout_group",
                    "pageId": "page-main",
                    "parentId": None,
                    "tabId": None,
                    "surface": "none",
                    "showBorder": True,
                    "showBackground": False,
                    "contentAlignment": "left",
                    "verticalAlignment": "top",
                    "padding": 8,
                    "spacing": 0,
                    "contentWidth": "stretch",
                    "heightMode": "fixed",
                    "elementFontSize": "auto",
                    "elementTextColor": "#d4d4d8",
                    "elementFontWeight": "normal",
                    "elementFontStyle": "normal",
                    "datasetId": None,
                    "order": 9,
                    "layout": {"x": 0, "y": 40, "width": 12, "height": 524},
                    "title": "",
                    "direction": "vertical",
                    "gap": 8,
                    "horizontalAlignment": "left",
                    "wrap": True,
                },
                {
                    "id": "page_link-d8dcb409-f91b-4742-9feb-a709835d93b7",
                    "type": "page_link",
                    "pageId": "page-main",
                    "parentId": None,
                    "tabId": None,
                    "surface": "card",
                    "showBorder": False,
                    "showBackground": False,
                    "contentAlignment": "right",
                    "verticalAlignment": "center",
                    "padding": 12,
                    "spacing": 16,
                    "contentWidth": "content",
                    "heightMode": "fixed",
                    "elementFontSize": 20,
                    "elementTextColor": "#d65f59",
                    "elementFontWeight": "normal",
                    "elementFontStyle": "normal",
                    "datasetId": None,
                    "order": 11,
                    "layout": {"x": 3, "y": 0, "width": 2, "height": 160},
                    "title": "Открыть страницу",
                    "targetPageId": page_two_id,
                    "displayStyle": "button",
                    "buttonColor": "#7656c8",
                },
                {
                    "id": "bar_chart-4442c4a1-eb59-4193-98aa-1d9cdb014fe9",
                    "type": "bar_chart",
                    "pageId": "page-main",
                    "parentId": group_id,
                    "tabId": None,
                    "surface": "card",
                    "showBorder": True,
                    "showBackground": True,
                    "contentAlignment": "left",
                    "verticalAlignment": "top",
                    "padding": 12,
                    "spacing": 0,
                    "contentWidth": "stretch",
                    "heightMode": "fixed",
                    "elementFontSize": "auto",
                    "elementTextColor": "#d4d4d8",
                    "elementFontWeight": "normal",
                    "elementFontStyle": "normal",
                    "datasetId": dataset_id,
                    "order": 13,
                    "layout": {"x": 0, "y": 0, "width": 6, "height": 320},
                    "title": "",
                    "x": "category",
                    "y": "cost",
                    "aggregation": "mean",
                    "sort": "asc",
                    "sortBy": "y",
                    "color": "#3478c8",
                    "colorMode": "gradient",
                    "palette": ["#9b62b5", "#7567c9", "#4e78c7", "#3478c8"],
                    "axisLabelFontSize": 11,
                    "axisLabelColor": "#94a3b8",
                    "axisTitleFontSize": 12,
                    "axisTitleColor": "#94a3b8",
                },
                {
                    "id": "text-69286060-1a91-4269-9e5f-e9c1a6c29735",
                    "type": "text",
                    "pageId": "page-main",
                    "parentId": None,
                    "tabId": None,
                    "surface": "card",
                    "showBorder": False,
                    "showBackground": False,
                    "contentAlignment": "left",
                    "verticalAlignment": "top",
                    "padding": 24,
                    "spacing": 0,
                    "contentWidth": "content",
                    "heightMode": "fixed",
                    "elementFontSize": "auto",
                    "elementTextColor": "#d4d4d8",
                    "elementFontWeight": "normal",
                    "elementFontStyle": "normal",
                    "datasetId": None,
                    "order": 14,
                    "layout": {"x": 5, "y": 0, "width": 3, "height": 160},
                    "title": "",
                    "content": "Анализ продаж",
                    "fontSize": 32,
                    "fontWeight": "normal",
                    "fontStyle": "normal",
                    "color": "#d4d4d8",
                    "textAlign": "center",
                },
            ],
        }

    def test_realistic_showcase_dashboard_runs_end_to_end_in_apptest(self):
        validated = validate_dashboard_schema(self._make_realistic_showcase_schema())
        code = generate_streamlit_code(validated)
        compile(code, "showcase_app.py", "exec")

        csv_content = "\n".join([
            "order_id,date,month,region,category,product,channel,customer_segment,quantity,unit_price,discount,revenue,cost,profit,satisfaction_score",
            "1,2026-01-10,2026-01,North,Electronics,Phone,Online,B2C,2,500,0,1000,600,400,4.8",
            "2,2026-01-20,2026-01,North,Home,Lamp,Retail,B2C,1,200,0,200,120,80,4.5",
            "3,2026-02-05,2026-02,South,Electronics,Laptop,Online,B2B,1,1800,0,1800,1100,700,4.9",
        ])

        with tempfile.TemporaryDirectory() as directory:
            project_dir = Path(directory)
            data_dir = project_dir / "data"
            data_dir.mkdir()
            (project_dir / "app.py").write_text(code, encoding="utf-8")
            (data_dir / "dashboard_showcase.csv").write_text(csv_content, encoding="utf-8")

            app = AppTest.from_file(project_dir / "app.py", default_timeout=20)
            app.run()

            self.assertEqual(len(app.exception), 0)
            # Page 1: root region filter + nested category filter, date data_control, mean revenue metric, navigation button.
            self.assertEqual(len(app.selectbox), 2)
            self.assertEqual(len(app.date_input), 1)
            self.assertEqual(len(app.button), 1)
            self.assertEqual(app.metric[0].value, "1 000.00")

            # Root filter narrows revenue mean to North rows (1000, 200 -> 600.00).
            app.selectbox[0].select("North").run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.metric[0].value, "600.00")

            # Nested filter inside layout_group further narrows to Home row (200.00).
            app.selectbox[1].select("Home").run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(app.metric[0].value, "200.00")

            # Clicking the page_link button switches to page 2 with the full table.
            app.button[0].click().run()
            self.assertEqual(len(app.exception), 0)
            self.assertEqual(len(app.dataframe), 1)
            self.assertEqual(len(app.button), 1)


# --- Runtime renderer (render_core) behavior ---


class RuntimeRendererTests(unittest.TestCase):
    def test_chart_supports_the_same_field_on_both_axes(self):
        dataframe = pd.DataFrame({"price": [1, 2, 2, 3]})
        plot_df, x_type = render_core.prepare_plot_frame({
            "type": "area_chart",
            "x": "price",
            "y": "price",
            "aggregation": "sum",
            "sort": "asc",
            "sortBy": "x",
            "layout": {"width": 6, "height": 320},
        }, dataframe)

        self.assertEqual(x_type, "quantitative")
        self.assertEqual(plot_df["x"].tolist(), [1, 2, 3])
        self.assertEqual(plot_df["y"].tolist(), [1.0, 4.0, 3.0])

    def test_progress_content_width_is_mapped_to_supported_pixel_width(self):
        component = {
            "id": "progress-1",
            "type": "progress",
            "field": "value",
            "aggregation": "mean",
            "minimum": 0,
            "maximum": 100,
            "contentWidth": "content",
        }
        dataframe = pd.DataFrame({"value": [20, 40]})

        with patch.object(render_core.st, "progress") as progress_mock:
            render_core.render_progress(component, dataframe)

        self.assertEqual(progress_mock.call_args.kwargs["width"], 280)

    def test_progress_rejects_an_empty_range_without_dividing_by_zero(self):
        component = {
            "id": "progress-1",
            "type": "progress",
            "field": "value",
            "aggregation": "mean",
            "minimum": 10,
            "maximum": 10,
        }
        dataframe = pd.DataFrame({"value": [10]})

        with (
            patch.object(render_core.st, "warning") as warning_mock,
            patch.object(render_core.st, "progress") as progress_mock,
        ):
            render_core.render_progress(component, dataframe)

        warning_mock.assert_called_once()
        progress_mock.assert_not_called()

    def test_auto_height_text_wraps_its_content_even_with_border(self):
        component = {
            "id": "text-1",
            "type": "text",
            "content": "Короткий текст",
            "heightMode": "auto",
            "showBorder": True,
            "showBackground": True,
            "layout": {"height": 180},
        }

        with (
            patch.object(render_core.st, "container") as container_mock,
            patch.object(render_core, "render_text"),
        ):
            render_core.render_component(
                component,
                None,
                None,
                container_height=200,
            )

        self.assertEqual(container_mock.call_args.kwargs["height"], "content")
        self.assertTrue(container_mock.call_args.kwargs["border"])

    def test_nested_components_receive_their_own_styles(self):
        group = {
            "id": "navigation",
            "type": "layout_group",
            "order": 1,
            "elementTextColor": "#84cc16",
            "layout": {"width": 3, "height": 240},
        }
        link = {
            "id": "page-link",
            "type": "page_link",
            "parentId": "navigation",
            "order": 2,
            "elementTextColor": "#60a5fa",
            "layout": {"height": 60},
        }
        style = render_core.dashboard_grid_style(
            [{"x": 0, "y": 0, "w": 3, "h": 4, "component": group}],
            [group, link],
        )

        self.assertIn("st-key-card_builder_filter_navigation", style)
        self.assertIn("st-key-card_builder_filter_page_link", style)
        self.assertIn("color: #60a5fa !important", style)

    def test_grouped_page_link_uses_fixed_render_height(self):
        component = {
            "id": "link-1",
            "type": "page_link",
            "showBorder": True,
            "showBackground": True,
            "layout": {"height": 120},
        }

        with (
            patch.object(render_core.st, "container") as container_mock,
            patch.object(render_core, "render_page_link"),
        ):
            render_core.render_component(
                component,
                None,
                None,
                navigation_pages={},
                grouped=True,
            )

        self.assertEqual(
            container_mock.call_args.kwargs["height"],
            120 + render_core.CARD_CHROME_HEIGHT - 44,
        )

    def test_page_link_does_not_create_a_visible_card(self):
        component = {
            "id": "link-1",
            "type": "page_link",
            "title": "Подробнее",
            "targetPageId": "page-details",
            "displayStyle": "link",
            "layout": {"height": 60},
        }

        with (
            patch.object(render_core.st, "container") as container_mock,
            patch.object(render_core, "render_page_link"),
        ):
            render_core.render_component(
                component,
                None,
                None,
                container_height=92,
                navigation_pages={"page-details": object()},
            )

        self.assertEqual(container_mock.call_args.kwargs["height"], 92)
        self.assertFalse(container_mock.call_args.kwargs["border"])

    def test_table_renderer_uses_filtered_rows_and_selected_columns(self):
        component = {
            "columns": ["region", "sales"],
            "rowLimit": 2,
            "hideIndex": True,
        }
        dataframe = pd.DataFrame({
            "region": ["A", "B", "C"],
            "sales": [10, 20, 30],
            "internal": [1, 2, 3],
        })

        with patch.object(render_core.st, "dataframe") as dataframe_mock:
            render_core.render_table(component, dataframe, 220)

        rendered = dataframe_mock.call_args.args[0]
        self.assertEqual(list(rendered.columns), ["region", "sales"])
        self.assertEqual(len(rendered), 2)
        self.assertEqual(dataframe_mock.call_args.kwargs["height"], "content")

    def test_table_renderer_can_show_all_rows(self):
        component = {"columns": ["region"], "rowMode": "all", "rowLimit": 1}
        dataframe = pd.DataFrame({"region": ["A", "B", "C"]})

        with patch.object(render_core.st, "dataframe") as dataframe_mock:
            render_core.render_table(component, dataframe, 220)

        self.assertEqual(len(dataframe_mock.call_args.args[0]), 3)

    def test_table_renderer_builds_pivot_table(self):
        component = {
            "tableMode": "pivot", "rowMode": "all",
            "pivotIndex": "region", "pivotValue": "sales",
            "pivotAggregation": "sum",
        }
        dataframe = pd.DataFrame({
            "region": ["A", "A", "B"],
            "sales": [10, 15, 20],
        })

        with patch.object(render_core.st, "dataframe") as dataframe_mock:
            render_core.render_table(component, dataframe, 220)

        rendered = dataframe_mock.call_args.args[0]
        self.assertEqual(rendered.to_dict("records"), [
            {"region": "A", "sales": 25},
            {"region": "B", "sales": 20},
        ])

    def test_multiselect_filter_accepts_multiple_values(self):
        schema = {
            "filters": [{
                "id": "filter-1",
                "type": "selectbox",
                "field": "region",
                "widget": "multiselect",
                "datasetId": "dataset-1",
                "order": 1,
            }],
        }
        datasets = {
            "dataset-1": pd.DataFrame({
                "region": ["A", "B", "C"],
                "sales": [10, 20, 30],
            }),
        }

        with patch.object(
            render_core,
            "selected_filter_value",
            return_value=["A", "C"],
        ):
            filtered = render_core.apply_filters(schema, datasets)

        self.assertEqual(filtered["dataset-1"]["region"].tolist(), ["A", "C"])

    def test_metric_renderer_uses_native_streamlit_component(self):
        component = {
            "title": "Продажи",
            "field": "sales",
            "aggregation": "sum",
            "layout": {"height": 80},
        }
        dataframe = pd.DataFrame({"sales": [10, 20]})

        with patch.object(render_core.st, "metric") as metric_mock:
            render_core.render_metric(component, dataframe)

        metric_mock.assert_called_once_with(
            label="Продажи",
            value="30",
            help=None,
            label_visibility="visible",
            border=False,
            width="stretch",
            height="content",
        )

    def test_metric_renderer_collapses_automatic_label(self):
        component = {
            "title": "",
            "field": "sales",
            "aggregation": "sum",
        }
        dataframe = pd.DataFrame({"sales": [10, 20]})

        with patch.object(render_core.st, "metric") as metric_mock:
            render_core.render_metric(component, dataframe)

        self.assertEqual(metric_mock.call_args.kwargs["label"], "sales")
        self.assertEqual(
            metric_mock.call_args.kwargs["label_visibility"],
            "collapsed",
        )

    def test_metric_renderer_uses_optional_description_as_help(self):
        component = {
            "title": "Продажи",
            "description": "Сумма за период",
            "field": "sales",
            "aggregation": "sum",
        }
        dataframe = pd.DataFrame({"sales": [10, 20]})

        with patch.object(render_core.st, "metric") as metric_mock:
            render_core.render_metric(component, dataframe)

        self.assertEqual(metric_mock.call_args.kwargs["help"], "Сумма за период")

    def test_compact_components_use_shorter_grid_rows(self):
        metric = {"type": "metric", "layout": {"height": 140}}
        text = {"type": "text", "layout": {"height": 60}}
        selectbox = {"type": "selectbox", "layout": {"height": 80}}

        self.assertEqual(render_core.grid_height(metric), 6)
        self.assertEqual(render_core.grid_height(text), 2)
        self.assertEqual(render_core.grid_height(selectbox), 4)

    def test_manually_resized_text_keeps_fixed_height(self):
        text = {
            "type": "text",
            "heightMode": "fixed",
            "layout": {"height": 160},
        }

        self.assertEqual(render_core.grid_height(text), 6)

    def test_renderer_keeps_editor_grid_coordinates(self):
        components = [
            {"type": "metric", "order": 1, "layout": {"x": 0, "y": 0, "width": 3, "height": 140}},
            {"type": "bar_chart", "order": 2, "layout": {"x": 0, "y": 7, "width": 3, "height": 248}},
            {"type": "line_chart", "order": 3, "layout": {"x": 3, "y": 0, "width": 6, "height": 320}},
            {"type": "text", "order": 4, "layout": {"x": 3, "y": 12, "width": 6, "height": 60}},
        ]

        metric, bar, line, text = render_core.pack_components(components)

        self.assertEqual((metric["y"], metric["h"]), (0, 6))
        self.assertEqual((bar["y"], bar["h"]), (7, 13))
        self.assertEqual((line["y"], line["h"]), (0, 16))
        self.assertEqual((text["y"], text["h"]), (16, 2))

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

    def test_text_renderer_uses_native_markdown_for_default_style(self):
        component = {
            "title": "Комментарий",
            "content": "Обычный текст",
        }

        with patch.object(render_core.st, "markdown") as markdown_mock:
            render_core.render_text(component)

        self.assertEqual(markdown_mock.call_args_list[0].args[0], "**Комментарий**")
        self.assertEqual(markdown_mock.call_args_list[1].args[0], "Обычный текст")
        self.assertNotIn(
            "unsafe_allow_html",
            markdown_mock.call_args_list[1].kwargs,
        )

    # --- Data transformations (prepare_chart_data & calculate_metric) ---

    def test_prepare_chart_data_supports_all_aggregations_sorting_and_dirty_numbers(self):
        dataframe = pd.DataFrame({
            "region": ["A", "A", "B"],
            "sales": ["10", "15,5", "1 000"],
        })
        expected_by_agg = {
            "sum": [25.5, 1000.0],
            "mean": [12.75, 1000.0],
            "count": [2, 1],
            "min": [10.0, 1000.0],
            "max": [15.5, 1000.0],
        }
        for aggregation, expected in expected_by_agg.items():
            with self.subTest(aggregation=aggregation):
                result = render_core.prepare_chart_data(
                    dataframe,
                    "region",
                    "sales",
                    aggregation=aggregation,
                    sort_order="asc",
                    sort_by="x",
                )
                self.assertEqual(result["region"].tolist(), ["A", "B"])
                self.assertEqual(result["sales"].tolist(), expected)

        sorted_by_y = render_core.prepare_chart_data(
            dataframe,
            "region",
            "sales",
            aggregation="sum",
            sort_order="desc",
            sort_by="y",
        )
        self.assertEqual(sorted_by_y["region"].tolist(), ["B", "A"])

        # Count works on non-numeric string columns.
        non_numeric = pd.DataFrame({
            "region": ["A", "A", "B"],
            "order": ["first", "second", "third"],
        })
        counted = render_core.prepare_chart_data(
            non_numeric,
            "region",
            "order",
            aggregation="count",
            sort_order="asc",
        )
        self.assertEqual(counted["order"].tolist(), [2, 1])

        with self.assertRaises(KeyError):
            render_core.prepare_chart_data(dataframe, "missing", "sales")
        with self.assertRaises(ValueError):
            render_core.prepare_chart_data(dataframe, "region", "sales", aggregation="median")

    def test_calculate_metric_supports_all_aggregations_and_invalid_values(self):
        dataframe = pd.DataFrame({"value": ["10", "20,5", "1 000", None, "bad"]})

        self.assertEqual(render_core.calculate_metric(dataframe, "value", "sum"), 1030.5)
        self.assertEqual(render_core.calculate_metric(dataframe, "value", "mean"), 343.5)
        self.assertEqual(render_core.calculate_metric(dataframe, "value", "min"), 10)
        self.assertEqual(render_core.calculate_metric(dataframe, "value", "max"), 1000)
        # Count follows pandas semantics: every non-null source cell counts.
        self.assertEqual(render_core.calculate_metric(dataframe, "value", "count"), 4)

        all_invalid = pd.DataFrame({"value": [None, "", "bad"]})
        self.assertEqual(render_core.calculate_metric(all_invalid, "value", "sum"), 0)

        with self.assertRaises(KeyError):
            render_core.calculate_metric(dataframe, "missing", "sum")
        with self.assertRaises(ValueError):
            render_core.calculate_metric(dataframe, "value", "none")

    # --- Data controls and filter scoping ---

    def test_apply_filters_handles_data_controls_page_and_dataset_scoping(self):
        schema = {
            "filters": [
                {
                    "id": "range-1",
                    "type": "data_control",
                    "controlType": "range",
                    "field": "sales",
                    "datasetId": "ds-1",
                    "pageId": "page-main",
                    "order": 1,
                },
                {
                    "id": "date-1",
                    "type": "data_control",
                    "controlType": "date",
                    "field": "dt",
                    "datasetId": "ds-1",
                    "pageId": "page-main",
                    "order": 2,
                },
                {
                    "id": "toggle-1",
                    "type": "data_control",
                    "controlType": "toggle",
                    "field": "active",
                    "datasetId": "ds-1",
                    "pageId": "page-main",
                    "order": 3,
                },
                {
                    "id": "other-page-filter",
                    "type": "selectbox",
                    "field": "region",
                    "datasetId": "ds-1",
                    "pageId": "page-other",
                    "order": 4,
                },
            ]
        }
        datasets = {
            "ds-1": pd.DataFrame({
                "region": ["A", "B", "C", "D"],
                "sales": [5, 25, 50, 150],
                "dt": ["2026-01-01", "2026-01-10", "2026-01-15", "2026-02-01"],
                "active": [True, False, True, True],
            }),
            "ds-2": pd.DataFrame({"other": [1, 2, 3]}),
        }
        fake_state = {
            "builder_filter_range_1": (10, 100),
            "builder_filter_date_1": (date(2026, 1, 5), date(2026, 1, 20)),
            "builder_filter_toggle_1": True,
            # Must be ignored when applying filters for page-main.
            "builder_filter_other_page_filter": "A",
        }

        with patch.object(render_core.st, "session_state", fake_state):
            filtered = render_core.apply_filters(schema, datasets, page_id="page-main")

        # Only row "C" satisfies 10<=sales<=100, date in [Jan 5..20], and active=True.
        self.assertEqual(filtered["ds-1"]["region"].tolist(), ["C"])
        # Unrelated dataset must remain untouched.
        self.assertEqual(filtered["ds-2"]["other"].tolist(), [1, 2, 3])

    def test_render_data_control_dispatches_to_native_widgets_and_warns_on_missing_field(self):
        dataframe = pd.DataFrame({
            "sales": [10, 50],
            "dt": ["2026-01-01", "2026-01-10"],
            "active": [True, False],
        })

        with (
            patch.object(render_core.st, "session_state", {}),
            patch.object(render_core.st, "slider") as slider_mock,
            patch.object(render_core.st, "date_input") as date_mock,
            patch.object(render_core.st, "toggle") as toggle_mock,
            patch.object(render_core.st, "warning") as warning_mock,
        ):
            render_core.render_data_control(
                {"id": "c1", "field": "sales", "controlType": "range", "title": "Sales"},
                dataframe,
            )
            render_core.render_data_control(
                {"id": "c2", "field": "dt", "controlType": "date", "title": "Period"},
                dataframe,
            )
            render_core.render_data_control(
                {"id": "c3", "field": "active", "controlType": "toggle", "title": "Active"},
                dataframe,
            )
            render_core.render_data_control(
                {"id": "c4", "field": "missing", "controlType": "range"},
                dataframe,
            )

        slider_mock.assert_called_once()
        date_mock.assert_called_once()
        toggle_mock.assert_called_once()
        warning_mock.assert_called_once()

    # --- Chart Vega-Lite specs, helpers, and safe fallbacks ---

    def test_render_chart_builds_vega_lite_spec_for_palettes_and_hover_layers(self):
        dataframe = pd.DataFrame({
            "date": ["2026-01-01", "2026-01-02"],
            "region": ["A", "B"],
            "sales": [10, 25],
        })

        # Bar chart with gradient palette uses quantitative y color scale.
        with patch.object(render_core.st, "vega_lite_chart") as chart_mock:
            render_core.render_chart(
                {
                    "type": "bar_chart",
                    "x": "region",
                    "y": "sales",
                    "colorMode": "gradient",
                    "palette": ["#fbbf24", "#ef4444"],
                    "layout": {"width": 6, "height": 300},
                },
                dataframe,
                260,
            )
        bar_spec = chart_mock.call_args.args[1]
        self.assertEqual(bar_spec["mark"]["type"], "bar")
        self.assertEqual(bar_spec["encoding"]["color"]["field"], "y")
        self.assertEqual(bar_spec["encoding"]["color"]["scale"]["range"], ["#fbbf24", "#ef4444"])

        # Bar chart with categorical palette maps colors by label.
        with patch.object(render_core.st, "vega_lite_chart") as chart_mock:
            render_core.render_chart(
                {
                    "type": "bar_chart",
                    "x": "region",
                    "y": "sales",
                    "colorMode": "categorical",
                    "palette": ["#0ea5e9", "#8b5cf6"],
                    "layout": {"width": 6, "height": 300},
                },
                dataframe,
                260,
            )
        cat_spec = chart_mock.call_args.args[1]
        self.assertEqual(cat_spec["encoding"]["color"]["field"], "label")
        self.assertEqual(cat_spec["encoding"]["color"]["type"], "nominal")

        # Line chart builds layered hover rule + highlighted point.
        with patch.object(render_core.st, "vega_lite_chart") as chart_mock:
            render_core.render_chart(
                {
                    "type": "line_chart",
                    "x": "date",
                    "y": "sales",
                    "layout": {"width": 6, "height": 300},
                },
                dataframe,
                260,
            )
        line_spec = chart_mock.call_args.args[1]
        self.assertEqual(len(line_spec["layer"]), 3)
        self.assertEqual(line_spec["layer"][1]["mark"]["type"], "rule")
        self.assertEqual(line_spec["layer"][0]["encoding"]["x"]["type"], "temporal")

        # Scatter plot uses layered hover point overlay.
        with patch.object(render_core.st, "vega_lite_chart") as chart_mock:
            render_core.render_chart(
                {
                    "type": "scatter_plot",
                    "x": "sales",
                    "y": "sales",
                    "colorMode": "gradient",
                    "palette": ["#0ea5e9", "#ef4444"],
                    "layout": {"width": 6, "height": 300},
                },
                dataframe,
                260,
            )
        scatter_spec = chart_mock.call_args.args[1]
        self.assertEqual(len(scatter_spec["layer"]), 2)
        self.assertEqual(scatter_spec["layer"][0]["mark"]["type"], "point")

    def test_render_chart_shows_warning_or_info_on_missing_field_or_empty_data(self):
        dataframe = pd.DataFrame({"region": ["A"], "sales": [10]})

        with (
            patch.object(render_core.st, "warning") as warning_mock,
            patch.object(render_core.st, "vega_lite_chart") as chart_mock,
        ):
            render_core.render_chart(
                {"type": "bar_chart", "x": "missing", "y": "sales"},
                dataframe,
                260,
            )
        warning_mock.assert_called_once()
        chart_mock.assert_not_called()

        empty_df = pd.DataFrame({"region": pd.Series(dtype="object"), "sales": pd.Series(dtype="float64")})
        with (
            patch.object(render_core.st, "info") as info_mock,
            patch.object(render_core.st, "vega_lite_chart") as chart_mock,
        ):
            render_core.render_chart(
                {"type": "bar_chart", "x": "region", "y": "sales"},
                empty_df,
                260,
            )
        info_mock.assert_called_once()
        chart_mock.assert_not_called()

    def test_axis_tick_values_downsample_and_state_key_helpers(self):
        values = [f"2026-01-{day:02d}" for day in range(1, 32)]
        ticks = render_core.axis_tick_values(values, 6)
        self.assertEqual(len(ticks), 6)
        self.assertEqual(ticks[0], "2026-01-01")
        self.assertEqual(ticks[-1], "2026-01-31")

        large_df = pd.DataFrame({"x": list(range(100))})
        sampled = render_core.downsample_frame(large_df, 10)
        self.assertEqual(len(sampled), 10)
        self.assertEqual(sampled["x"].iloc[0], 0)
        self.assertEqual(sampled["x"].iloc[-1], 99)

        self.assertEqual(
            render_core.component_state_key({"id": "selectbox-123-abc"}),
            "builder_filter_selectbox_123_abc",
        )


if __name__ == "__main__":
    unittest.main()
