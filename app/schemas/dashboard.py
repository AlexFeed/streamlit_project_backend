from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Aggregation = Literal["none", "sum", "mean", "count", "min", "max"]
SortOrder = Literal["none", "asc", "desc"]
FilterWidget = Literal["selectbox", "radio", "segmented", "pills", "multiselect"]
Surface = Literal["none", "soft", "card"]
DEFAULT_PAGE_ID = "page-main"


class Layout(BaseModel):
    width: int = Field(default=6, ge=1, le=12)
    # Compact text can be one 40-48px row. Type-specific validation below
    # still keeps charts, tables and containers at their larger minimums.
    height: int = Field(default=320, ge=40, le=720)
    x: int | None = Field(default=None, ge=0, le=11)
    y: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def component_must_fit_grid(self):
        if self.x is not None and self.x + self.width > 12:
            raise ValueError("Component layout must fit within the 12-column grid")
        return self


class DashboardGrid(BaseModel):
    columns: Literal[12] = 12


class DashboardMeta(BaseModel):
    title: str = "Untitled dashboard"
    grid: DashboardGrid = Field(default_factory=DashboardGrid)


class DashboardPage(BaseModel):
    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    order: int = Field(ge=1)


def default_dashboard_pages():
    return [DashboardPage(id=DEFAULT_PAGE_ID, title="Главная", order=1)]


class DataSource(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["backend_dataset"] = "backend_dataset"
    dataset_id: str | None = Field(default=None, alias="datasetId")
    name: str = "data.csv"
    format: str | None = "csv"
    delimiter: str | None = None
    encoding: str | None = None
    sheet_name: str | None = Field(default=None, alias="sheetName")
    fields: list[str] = Field(default_factory=list)


class ComponentBase(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    page_id: str = Field(default=DEFAULT_PAGE_ID, alias="pageId")
    dataset_id: str | None = Field(default=None, alias="datasetId")
    parent_id: str | None = Field(default=None, alias="parentId")
    surface: Surface = "card"
    show_border: bool | None = Field(default=None, alias="showBorder")
    show_background: bool | None = Field(default=None, alias="showBackground")
    content_alignment: Literal["left", "center", "right"] = Field(
        default="left",
        alias="contentAlignment",
    )
    vertical_alignment: Literal["top", "center", "bottom"] = Field(
        default="top",
        alias="verticalAlignment",
    )
    padding: int = Field(default=12, ge=0, le=32)
    spacing: int = Field(default=0, ge=0, le=16)
    content_width: Literal["content", "stretch"] = Field(
        default="stretch",
        alias="contentWidth",
    )
    height_mode: Literal["auto", "fixed"] | None = Field(
        default=None,
        alias="heightMode",
    )
    element_font_size: str | int = Field(
        default="auto",
        alias="elementFontSize",
    )
    element_text_color: str = Field(
        default="#d4d4d8",
        alias="elementTextColor",
        pattern=r"^#[0-9a-fA-F]{6}$",
    )
    element_font_weight: Literal["normal", "bold"] = Field(
        default="normal",
        alias="elementFontWeight",
    )
    element_font_style: Literal["normal", "italic"] = Field(
        default="normal",
        alias="elementFontStyle",
    )
    order: int = Field(ge=1)
    layout: Layout = Field(default_factory=Layout)
    title: str = ""

    @field_validator("element_font_size")
    @classmethod
    def validate_element_font_size(cls, value):
        if value == "auto":
            return value
        try:
            numeric = int(value)
        except (TypeError, ValueError) as error:
            raise ValueError("Unsupported element font size") from error
        if numeric not in {12, 14, 16, 18, 20, 24, 28, 32}:
            raise ValueError("Unsupported element font size")
        return numeric


class SelectboxFilter(ComponentBase):
    type: Literal["selectbox"]
    field: str
    scope: Literal["global"] = "global"
    widget: FilterWidget = "selectbox"


class ChartView(ComponentBase):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    type: Literal["line_chart", "bar_chart", "area_chart", "scatter_plot"]
    x: str
    y: str
    aggregation: Aggregation = "none"
    sort: SortOrder = "none"
    sort_by: Literal["x", "y"] = Field(default="x", alias="sortBy")
    color: str = Field(default="#3b82f6", pattern=r"^#[0-9a-fA-F]{6}$")
    color_mode: Literal["solid", "gradient", "categorical"] = Field(
        default="solid",
        alias="colorMode",
    )
    palette: list[str] = Field(
        default_factory=lambda: [
            "#0ea5e9",
            "#3b82f6",
            "#6366f1",
            "#8b5cf6",
        ],
        min_length=2,
        max_length=8,
    )
    axis_label_font_size: int = Field(default=11, alias="axisLabelFontSize", ge=8, le=24)
    axis_label_color: str = Field(default="#94a3b8", alias="axisLabelColor", pattern=r"^#[0-9a-fA-F]{6}$")
    axis_title_font_size: int = Field(default=12, alias="axisTitleFontSize", ge=8, le=24)
    axis_title_color: str = Field(default="#94a3b8", alias="axisTitleColor", pattern=r"^#[0-9a-fA-F]{6}$")

    @field_validator("palette")
    @classmethod
    def palette_colors_must_be_hex(cls, colors):
        import re

        if any(not re.fullmatch(r"#[0-9a-fA-F]{6}", color) for color in colors):
            raise ValueError("Palette colors must use #RRGGBB format")
        return colors

    @model_validator(mode="after")
    def palette_mode_must_match_chart_type(self):
        if (
            self.type not in {"bar_chart", "scatter_plot"}
            and self.color_mode != "solid"
        ):
            raise ValueError(
                "Data-driven palettes are supported for bar and scatter charts"
            )
        return self


class MetricView(ComponentBase):
    type: Literal["metric"]
    field: str
    description: str = ""
    aggregation: Literal["sum", "mean", "count", "min", "max"] = "sum"


class TextView(ComponentBase):
    type: Literal["text"]
    surface: Surface = "none"
    content: str = Field(min_length=1)
    font_size: int = Field(default=16, alias="fontSize", ge=12, le=32)
    font_weight: Literal["normal", "bold"] = Field(
        default="normal",
        alias="fontWeight",
    )
    font_style: Literal["normal", "italic"] = Field(
        default="normal",
        alias="fontStyle",
    )
    color: str = Field(default="#d4d4d8", pattern=r"^#[0-9a-fA-F]{6}$")
    text_align: Literal["left", "center", "right"] = Field(
        default="left",
        alias="textAlign",
    )


class PageLinkView(ComponentBase):
    type: Literal["page_link"]
    surface: Surface = "none"
    target_page_id: str = Field(min_length=1, alias="targetPageId")
    display_style: Literal["button", "link"] = Field(
        default="button",
        alias="displayStyle",
    )
    button_color: str = Field(
        default="#f47721",
        alias="buttonColor",
        pattern=r"^#[0-9a-fA-F]{6}$",
    )


class TableView(ComponentBase):
    type: Literal["table"]
    columns: list[str] = Field(default_factory=list)
    table_mode: Literal["data", "pivot"] = Field(default="data", alias="tableMode")
    row_mode: Literal["all", "limit"] = Field(default="limit", alias="rowMode")
    row_limit: int = Field(default=50, alias="rowLimit", ge=1, le=10000)
    hide_index: bool = Field(default=True, alias="hideIndex")
    pivot_index: str = Field(default="", alias="pivotIndex")
    pivot_value: str = Field(default="", alias="pivotValue")
    pivot_aggregation: Literal["sum", "mean", "count", "min", "max"] = Field(
        default="sum",
        alias="pivotAggregation",
    )

    @model_validator(mode="after")
    def pivot_fields_are_required(self):
        if self.table_mode == "pivot" and (not self.pivot_index or not self.pivot_value):
            raise ValueError("Pivot tables require both grouping and value fields")
        return self


class LayoutGroupView(ComponentBase):
    type: Literal["layout_group"]
    surface: Surface = "none"
    direction: Literal["vertical", "horizontal"] = "vertical"
    gap: int = Field(default=8, ge=0, le=32)
    padding: int = Field(default=8, ge=0, le=32)
    horizontal_alignment: Literal["left", "center", "right", "distribute"] = Field(
        default="left",
        alias="horizontalAlignment",
    )
    vertical_alignment: Literal["top", "center", "bottom", "distribute"] = Field(
        default="top",
        alias="verticalAlignment",
    )
    wrap: bool = True


DashboardView = Annotated[
    Union[ChartView, MetricView, TextView, PageLinkView, TableView, LayoutGroupView],
    Field(discriminator="type"),
]


class DashboardSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: Literal[1, 2] = 2
    dashboard: DashboardMeta
    pages: list[DashboardPage] = Field(
        default_factory=default_dashboard_pages,
        min_length=1,
    )
    data_sources: list[DataSource] = Field(alias="dataSources", min_length=1)
    filters: list[SelectboxFilter] = Field(default_factory=list)
    views: list[DashboardView] = Field(default_factory=list)

    @field_validator("filters", "views")
    @classmethod
    def component_ids_must_be_unique_within_group(cls, components):
        ids = [component.id for component in components]
        if len(ids) != len(set(ids)):
            raise ValueError("Component ids must be unique")
        return components

    @field_validator("pages")
    @classmethod
    def page_ids_must_be_unique(cls, pages):
        ids = [page.id for page in pages]
        if len(ids) != len(set(ids)):
            raise ValueError("Page ids must be unique")
        return pages

    @model_validator(mode="after")
    def charts_must_keep_readable_height(self):
        page_ids = {page.id for page in self.pages}
        components = [*self.filters, *self.views]
        groups = {
            component.id: component
            for component in components
            if component.type == "layout_group"
        }
        for component in components:
            if component.page_id not in page_ids:
                raise ValueError(
                    f'Component page "{component.page_id}" does not exist'
                )
            if (
                component.type == "page_link"
                and component.target_page_id not in page_ids
            ):
                raise ValueError(
                    f'Target page "{component.target_page_id}" does not exist'
                )
            if (
                component.type not in {"text", "metric", "selectbox", "page_link", "layout_group"}
                and component.layout.height < 120
            ):
                raise ValueError(
                    "Chart height must be at least 120 pixels"
                )
            if component.type == "layout_group" and component.parent_id:
                raise ValueError("Layout groups cannot be nested")
            if component.parent_id:
                parent = groups.get(component.parent_id)
                if parent is None or parent.page_id != component.page_id:
                    raise ValueError("Component parent must be a layout group on the same page")
        return self


def validate_dashboard_schema(schema: dict) -> dict:
    validated = DashboardSchema.model_validate(schema)

    all_ids = [
        component.id
        for component in [*validated.filters, *validated.views]
    ]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("Component ids must be unique across dashboard")

    return validated.model_dump(by_alias=True)
