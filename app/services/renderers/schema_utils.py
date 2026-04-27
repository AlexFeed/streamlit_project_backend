# Базовые функции для обоих режимов генерации кода

def get_dashboard_title(schema: dict) -> str:
    return schema.get("dashboard", {}).get("title", "Untitled project")


def get_filters(schema: dict) -> list[dict]:
    filters = schema.get("filters", [])
    return sorted(filters, key=lambda item: item.get("order", 0))


def get_views(schema: dict) -> list[dict]:
    views = schema.get("views", [])
    return sorted(views, key=lambda item: item.get("order", 0))


def get_dataset_name(schema: dict) -> str:
    return schema.get("dataSource", {}).get("name", "data.csv")


def safe_string(value: str | None, fallback: str = "") -> str:
    if value is None:
        return fallback

    return str(value).replace("'", "\\'")


import re

def safe_variable_name(value: str, fallback: str = "value") -> str:
    result = re.sub(r"\W+", "_", str(value), flags=re.UNICODE).strip("_")

    if not result:
        return fallback

    if result[0].isdigit():
        result = f"_{result}"

    return result