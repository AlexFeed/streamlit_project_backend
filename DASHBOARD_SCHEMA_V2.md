# Dashboard Schema v2 — backend contract

Backend принимает декларативную схему из React-редактора и использует её как единственный источник для live preview и экспортируемого `app.py`.

## Поддерживаемые компоненты

| Type | Streamlit |
| --- | --- |
| `selectbox` | `st.selectbox` |
| `line_chart` | `st.line_chart` |
| `bar_chart` | `st.bar_chart` |
| `area_chart` | `st.area_chart` |
| `scatter_plot` | `st.scatter_chart` |
| `metric` | `st.metric` |

Каждый компонент содержит `layout.width`: `3`, `4`, `6`, `8` или `12`, а также `layout.height` от `120` до `720` пикселей. Renderers укладывают компоненты в 12-колоночные строки и передают высоту в Streamlit charts, metrics и containers.

Графики поддерживают:

- `aggregation`: `none`, `sum`, `mean`, `count`, `min`, `max`;
- `sort`: `none`, `asc`, `desc`;
- `sortBy`: `x` или `y`;
- `color`: цвет серии в HEX-формате `#RRGGBB`, одинаковый на Canvas и в Streamlit.
- `colorMode`: `solid`, `gradient` или `categorical`;
- `palette`: от 2 до 8 цветов `#RRGGBB`. Для расширенных режимов `bar_chart` и `scatter_plot` backend генерирует Altair chart внутри Streamlit.

Метрики поддерживают все агрегации кроме `none`.

## Live Canvas data

React-редактор строит графики сразу на Canvas и получает ограниченную выборку данных:

```http
GET /datasets/{dataset_id}/preview?limit=500
```

Максимальный limit — 1000 строк. Ответ содержит `rows`, `fields`, `fieldTypes` и `returnedRows`. Выборка используется только для интерфейса редактора и не сохраняется внутри схемы проекта.

## Preview lifecycle

- `POST /preview` — создать сессию;
- `PUT /preview/{session_id}` — обновить схему и увеличить revision;
- `GET /preview/{session_id}` — получить данные для Streamlit runtime;
- `DELETE /preview/{session_id}` — удалить сессию.

Неактивные сессии автоматически удаляются по TTL.

## Environment

| Variable | Default |
| --- | --- |
| `PREVIEW_PORT` | `8501` |
| `PREVIEW_HOST` | `127.0.0.1` |
| `PREVIEW_PUBLIC_URL` | `http://localhost:8501` |
| `PREVIEW_SESSION_TTL_SECONDS` | `1800` |
| `STREAMLIT_BUILDER_API_BASE` | `http://localhost:8000` |

## Tests

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\venv\Scripts\python.exe -B -m unittest discover -s tests -v
```
