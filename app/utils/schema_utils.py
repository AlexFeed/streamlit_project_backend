def get_dashboard_title(schema: dict) -> str:
    return schema.get("dashboard", {}).get("title", "Untitled project")


def python_string_literal(value: str | None, fallback: str = "") -> str:
    return repr(fallback if value is None else str(value))
