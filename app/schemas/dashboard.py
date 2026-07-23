from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Aggregation = Literal["none", "sum", "mean", "count", "min", "max"]
SortOrder = Literal["none", "asc", "desc"]


class Layout(BaseModel):
    width: int = Field(default=6, ge=1, le=12)
    height: int = Field(default=320, ge=120, le=720)
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


class DataSource(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    type: Literal["backend_dataset"] = "backend_dataset"
    dataset_id: str | None = Field(default=None, alias="datasetId")
    name: str = "data.csv"
    fields: list[str] = Field(default_factory=list)


class ComponentBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    order: int = Field(ge=1)
    layout: Layout = Field(default_factory=Layout)
    title: str = ""


class SelectboxFilter(ComponentBase):
    type: Literal["selectbox"]
    field: str
    scope: Literal["global"] = "global"


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


DashboardView = Annotated[
    Union[ChartView, MetricView],
    Field(discriminator="type"),
]


class DashboardSchema(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: Literal[1, 2] = 2
    dashboard: DashboardMeta
    data_source: DataSource = Field(alias="dataSource")
    filters: list[SelectboxFilter] = Field(default_factory=list)
    views: list[DashboardView] = Field(default_factory=list)

    @field_validator("filters", "views")
    @classmethod
    def component_ids_must_be_unique_within_group(cls, components):
        ids = [component.id for component in components]
        if len(ids) != len(set(ids)):
            raise ValueError("Component ids must be unique")
        return components


def validate_dashboard_schema(schema: dict) -> dict:
    validated = DashboardSchema.model_validate(schema)

    all_ids = [
        component.id
        for component in [*validated.filters, *validated.views]
    ]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("Component ids must be unique across dashboard")

    return validated.model_dump(by_alias=True)
