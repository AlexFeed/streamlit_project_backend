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


def safe_variable_name(value: str) -> str:
    result = str(value)

    for symbol in [" ", "-", ".", ",", ":", ";", "/", "\\"]:
        result = result.replace(symbol, "_")

    return result