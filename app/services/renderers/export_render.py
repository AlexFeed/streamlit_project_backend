import inspect

from app.services.renderers import render_core

# Calls render_core to generate code and packages it into the final app.py file
def render_export_dashboard_code(schema: dict) -> list[str]:
    # Read the source code of render_core.py
    core_code = inspect.getsource(render_core)
    return [
        f"DASHBOARD_SCHEMA = {schema!r}",
        "",
        *core_code.strip().splitlines(),
        "",
        "render_multipage_dashboard(DASHBOARD_SCHEMA, datasets)",
        "",
    ]
