import re
from collections.abc import Iterable


GRID_COLUMNS = 12
GRID_ROW_HEIGHT = 20
GRID_GAP = 16


# Базовые функции для обоих режимов генерации кода

def get_dashboard_title(schema: dict) -> str:
    return schema.get("dashboard", {}).get("title", "Untitled project")


def get_filters(schema: dict) -> list[dict]:
    filters = schema.get("filters", [])
    return sorted(filters, key=lambda item: item.get("order", 0))


def get_views(schema: dict) -> list[dict]:
    views = schema.get("views", [])
    return sorted(views, key=lambda item: item.get("order", 0))


def get_components(schema: dict) -> list[dict]:
    components = [
        *schema.get("filters", []),
        *schema.get("views", []),
    ]
    return sorted(components, key=lambda item: item.get("order", 0))


def get_dataset_name(schema: dict) -> str:
    return schema.get("dataSource", {}).get("name", "data.csv")


def get_component_width(component: dict) -> int:
    width = component.get("layout", {}).get("width", 6)
    return width if isinstance(width, int) and 1 <= width <= 12 else 6


def get_component_height(component: dict, fallback: int = 320) -> int:
    height = component.get("layout", {}).get("height", fallback)

    if isinstance(height, int) and 120 <= height <= 720:
        return height

    return fallback


def get_component_grid_height(component: dict) -> int:
    cell_height = GRID_ROW_HEIGHT + GRID_GAP
    requested_height = get_component_height(component)
    return max(
        4,
        (requested_height + GRID_GAP + cell_height - 1) // cell_height,
    )


def pack_freeform_grid(components: Iterable[dict]) -> list[dict]:
    placed: list[dict] = []

    def overlaps(candidate: dict, item: dict) -> bool:
        return (
            candidate["x"] < item["x"] + item["w"]
            and candidate["x"] + candidate["w"] > item["x"]
            and candidate["y"] < item["y"] + item["h"]
            and candidate["y"] + candidate["h"] > item["y"]
        )

    ordered = sorted(components, key=lambda item: item.get("order", 0))
    explicit = []
    automatic = []

    for component in ordered:
        layout = component.get("layout", {})
        if isinstance(layout.get("x"), int) and isinstance(layout.get("y"), int):
            explicit.append(component)
        else:
            automatic.append(component)

    for component in explicit:
        layout = component.get("layout", {})
        width = get_component_width(component)
        x = max(0, min(GRID_COLUMNS - width, int(layout.get("x", 0))))
        placed.append({
            "x": x,
            "y": max(0, int(layout.get("y", 0))),
            "w": width,
            "h": get_component_grid_height(component),
            "component": component,
        })

    for component in automatic:
        width = get_component_width(component)
        height = get_component_grid_height(component)
        position = None

        for y in range(10000):
            for x in range(GRID_COLUMNS - width + 1):
                candidate = {"x": x, "y": y, "w": width, "h": height}
                if not any(overlaps(candidate, item) for item in placed):
                    position = candidate
                    break
            if position:
                break

        placed.append({
            **(position or {"x": 0, "y": 0, "w": width, "h": height}),
            "component": component,
        })

    return sorted(placed, key=lambda item: item["component"].get("order", 0))


def get_summary_components(schema: dict) -> list[dict]:
    components = [
        *schema.get("filters", []),
        *[
            view
            for view in schema.get("views", [])
            if view.get("type") == "metric"
        ],
    ]
    return sorted(components, key=lambda item: item.get("order", 0))


def get_chart_views(schema: dict) -> list[dict]:
    views = [
        view
        for view in schema.get("views", [])
        if view.get("type") != "metric"
    ]
    return sorted(views, key=lambda item: item.get("order", 0))


def pack_equal_rows(
    components: Iterable[dict],
    row_size: int = 4,
) -> list[list[dict]]:
    items = list(components)
    return [
        items[index:index + row_size]
        for index in range(0, len(items), row_size)
    ]


def balance_components_by_height(
    components: Iterable[dict],
    lane_count: int = 2,
) -> list[list[dict]]:
    lanes: list[list[dict]] = [[] for _ in range(lane_count)]
    heights = [0 for _ in range(lane_count)]

    for component in components:
        lane_index = min(
            range(lane_count),
            key=lambda index: heights[index],
        )
        lanes[lane_index].append(component)
        heights[lane_index] += get_component_height(component)

    return lanes


def pack_component_rows(components: Iterable[dict]) -> list[list[dict]]:
    rows: list[list[dict]] = []
    current_row: list[dict] = []
    occupied_columns = 0

    for component in components:
        width = get_component_width(component)

        if current_row and occupied_columns + width > GRID_COLUMNS:
            rows.append(current_row)
            current_row = []
            occupied_columns = 0

        current_row.append(component)
        occupied_columns += width

        if occupied_columns == GRID_COLUMNS:
            rows.append(current_row)
            current_row = []
            occupied_columns = 0

    if current_row:
        rows.append(current_row)

    return rows


def get_row_column_widths(row: list[dict]) -> list[int]:
    widths = [get_component_width(component) for component in row]
    remaining = GRID_COLUMNS - sum(widths)

    if remaining > 0:
        widths.append(remaining)

    return widths


def safe_string(value: str | None, fallback: str = "") -> str:
    if value is None:
        return fallback

    return str(value).replace("\\", "\\\\").replace("'", "\\'")


def python_string_literal(value: str | None, fallback: str = "") -> str:
    return repr(fallback if value is None else str(value))


def safe_variable_name(value: str, fallback: str = "value") -> str:
    result = re.sub(r"\W+", "_", str(value), flags=re.UNICODE).strip("_")

    if not result:
        return fallback

    if result[0].isdigit():
        result = f"_{result}"

    return result
