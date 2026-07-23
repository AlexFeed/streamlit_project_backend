import streamlit as st
from streamlit_elements import dashboard, elements, mui, nivo

from app.services.renderers.data_transform import (
    calculate_metric,
    prepare_chart_data,
)
from app.services.renderers.elements_export_render import (
    ELEMENTS_RENDERER_SOURCE,
    PAGE_STYLE,
)
from app.services.renderers.schema_utils import get_dashboard_title


_renderer_namespace = {
    "st": st,
    "dashboard": dashboard,
    "elements": elements,
    "mui": mui,
    "nivo": nivo,
    "calculate_metric": calculate_metric,
    "prepare_chart_data": lambda dataframe, x, y, aggregation, sort, sort_by: (
        prepare_chart_data(
            dataframe,
            {
                "x": x,
                "y": y,
                "aggregation": aggregation,
                "sort": sort,
                "sortBy": sort_by,
            },
        )
    ),
}
exec(ELEMENTS_RENDERER_SOURCE, _renderer_namespace)
render_elements_dashboard = _renderer_namespace["render_dashboard"]


def render_runtime_dashboard(schema: dict, df) -> None:
    st.markdown(PAGE_STYLE, unsafe_allow_html=True)
    st.title(get_dashboard_title(schema))
    st.caption("Интерактивный дашборд, созданный в Streamlit Builder")
    render_elements_dashboard(schema, df)
