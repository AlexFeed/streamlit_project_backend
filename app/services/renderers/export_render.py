import inspect
from app.services.renderers import render_core

# Вызывает render_core для генерации кода и упаковывает его в итоговый app.py файл
def render_export_dashboard_code(schema: dict) -> list[str]:
    # Берём исходный код render_core.py
    core_code = inspect.getsource(render_core)
    return [
        f"DASHBOARD_SCHEMA = {schema!r}",
        "",
        *core_code.strip().splitlines(),
        "",
        "render_dashboard(DASHBOARD_SCHEMA, datasets)",
        "",
    ]