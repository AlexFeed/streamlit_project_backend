from typing import Any

import pandas as pd


SUPPORTED_AGGREGATIONS = {"none", "sum", "mean", "count", "min", "max"}
SUPPORTED_SORT_ORDERS = {"none", "asc", "desc"}
SUPPORTED_SORT_FIELDS = {"x", "y"}
BUILDER_COLOR_COLUMN = "__builder_color__"


def prepare_chart_data(dataframe, view: dict):
    x = view.get("x")
    y = view.get("y")

    if not x or not y:
        raise ValueError("Для графика должны быть выбраны поля X и Y")

    missing_fields = [field for field in (x, y) if field not in dataframe.columns]
    if missing_fields:
        raise KeyError(", ".join(missing_fields))

    aggregation = view.get("aggregation", "none")
    sort_order = view.get("sort", "none")
    sort_by = view.get("sortBy", "x")

    if aggregation not in SUPPORTED_AGGREGATIONS:
        raise ValueError(f"Неизвестная агрегация: {aggregation}")
    if sort_order not in SUPPORTED_SORT_ORDERS:
        raise ValueError(f"Неизвестная сортировка: {sort_order}")
    if sort_by not in SUPPORTED_SORT_FIELDS:
        raise ValueError(f"Неизвестное поле сортировки: {sort_by}")

    chart_df = dataframe[[x, y]].dropna().copy()
    if chart_df.empty:
        return chart_df

    if aggregation != "count":
        chart_df[y] = pd.to_numeric(chart_df[y], errors="coerce")
        chart_df = chart_df.dropna(subset=[y])

    if aggregation != "none":
        chart_df = (
            chart_df
            .groupby(x, as_index=False, dropna=False)[y]
            .agg(aggregation)
        )

    if sort_order != "none":
        chart_df = chart_df.sort_values(
            by=y if sort_by == "y" else x,
            ascending=sort_order == "asc",
            kind="stable",
        )

    return chart_df


def calculate_metric(dataframe, field: str, aggregation: str) -> Any:
    if not field or field not in dataframe.columns:
        raise KeyError(field)

    if aggregation == "count":
        return int(dataframe[field].count())

    if aggregation not in SUPPORTED_AGGREGATIONS - {"none"}:
        raise ValueError(f"Неизвестная агрегация: {aggregation}")

    values = pd.to_numeric(dataframe[field], errors="coerce").dropna()
    if values.empty:
        return 0

    result = values.agg(aggregation)
    return result.item() if hasattr(result, "item") else result


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    return (
        int(value[0:2], 16),
        int(value[2:4], 16),
        int(value[4:6], 16),
    )


def _interpolate_color(
    value: float,
    minimum: float,
    maximum: float,
    palette: list[str],
) -> str:
    if minimum == maximum or len(palette) == 1:
        return palette[0]

    normalized = max(0.0, min(1.0, (value - minimum) / (maximum - minimum)))
    position = normalized * (len(palette) - 1)
    left_index = int(position)
    right_index = min(len(palette) - 1, left_index + 1)
    progress = position - left_index
    left = _hex_to_rgb(palette[left_index])
    right = _hex_to_rgb(palette[right_index])
    channels = [
        round(left[channel] + (right[channel] - left[channel]) * progress)
        for channel in range(3)
    ]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def apply_chart_palette(dataframe, view: dict):
    color_mode = view.get("colorMode", "solid")
    palette = view.get("palette") or ["#0ea5e9", "#8b5cf6"]

    if color_mode not in {"gradient", "categorical"}:
        return dataframe, view.get("color", "#3b82f6")

    chart_df = dataframe.copy()
    x = view.get("x")
    y = view.get("y")

    if color_mode == "gradient":
        values = pd.to_numeric(chart_df[y], errors="coerce")
        minimum = float(values.min())
        maximum = float(values.max())
        chart_df[BUILDER_COLOR_COLUMN] = values.map(
            lambda value: _interpolate_color(
                float(value),
                minimum,
                maximum,
                palette,
            )
        )
    else:
        categories = list(dict.fromkeys(chart_df[x].astype(str).tolist()))
        color_by_category = {
            category: palette[index % len(palette)]
            for index, category in enumerate(categories)
        }
        chart_df[BUILDER_COLOR_COLUMN] = (
            chart_df[x].astype(str).map(color_by_category)
        )

    return chart_df, BUILDER_COLOR_COLUMN
