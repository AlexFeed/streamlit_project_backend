**English** | [Русский](README.ru.md)

# Streamlit Dashboard Generator API (Backend)

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/python-3.14-blue.svg?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Pandas](https://img.shields.io/badge/pandas-%23150458.svg?style=for-the-badge&logo=pandas&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

A **FastAPI**-based backend service for the [`streamlit_project`](https://github.com/AlexFeed/streamlit_project) dashboard builder. Responsible for authentication, dataset uploads, project storage, **Dashboard Schema v2** validation, built-in **Streamlit** preview, and packaging a standalone Python project into a ZIP archive.

---

## 📌 Key Features

1. **Authentication & Accounts:** user registration (with an optional `name` field), **JWT (OAuth2 Bearer)** login with **Argon2** password hashing, and password updates (`PUT /auth/password`).
2. **Dataset Handling:** upload `.csv`, `.tsv`, `.xlsx`, and `.xls` files with delimiter selection, automatic detection and selection of character encoding (`encoding`), Excel sheet selection, and automatic column type inference (`number`, `datetime`, `boolean`, `string`).
3. **Editor Canvas Data:** fast row sampling (`GET /datasets/{id}/preview`, up to `10000` rows) for rendering charts, tables, and KPI metrics directly in the browser with **Recharts**.
4. **Dashboard Schema Validation:** strict **Dashboard Schema v2** validation via **Pydantic v2** — multi-page dashboards (`pages`), multiple datasets per project (`dataSources`), a 12-column grid, and 13 component types.
5. **Project Code Export:** generates a standalone Streamlit application packaged as a ZIP archive (`app.py`, `data/*`, `requirements.txt`, `README.md`, `run_local.bat`, `run_local.sh`).
6. **Streamlit Preview:** built-in **Streamlit** server (port `8501`) for testing the actual generated dashboard without downloading the archive (inactive sessions are automatically cleaned up by TTL).
7. **Storage & Data Isolation:** disk persistence for projects and datasets with strict isolation per user.

---

## 🚀 Getting Started

### Option 1. Run the Full Platform with Docker

You normally do not need to run this repository in Docker standalone — the entire platform (web editor, backend API, and built-in Streamlit preview) starts with a single command.

The prebuilt backend Docker image (`ghcr.io/alexfeed/streamlit_project_backend:latest`) is configured in the shared [`docker-compose.yml`](https://github.com/AlexFeed/streamlit_project/blob/main/docker-compose.yml) inside the frontend repository [`streamlit_project`](https://github.com/AlexFeed/streamlit_project), which also contains step-by-step Docker setup instructions.

**What the backend container does in `docker-compose.yml`:**
* exposes port `8000` (FastAPI REST API and Swagger UI) and port `8501` (Streamlit preview server);
* persists accounts, projects, and uploaded files in the shared `/app/storage` Docker volume.

If you need to debug or build the image locally, use [`Dockerfile`](Dockerfile):
```bash
docker build -t streamlit-builder-backend .
```

---

### Option 2. Local Development from Source

Suitable for developers who want to run and extend the API, schema validation, or Streamlit code generator locally.

> **Important:** this repository contains only the server-side service. To work with the visual builder in your browser, you also need to run the web editor from [`streamlit_project`](https://github.com/AlexFeed/streamlit_project) (see its `README.md` for setup instructions).

**Requirements:** Python **3.14** (the same version is used in [`Dockerfile`](Dockerfile) and CI).

1. Clone the repository and navigate to the project folder:
   ```bash
   git clone https://github.com/AlexFeed/streamlit_project_backend.git
   cd streamlit_project_backend
   ```
2. Create and activate a virtual environment:
   * **Windows (PowerShell / CMD):**
     ```powershell
     python -m venv .venv
     .venv\Scripts\activate
     ```
   * **macOS / Linux:**
     ```bash
     python3 -m venv .venv
     source .venv/bin/activate
     ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the server:
   ```bash
   uvicorn app.main:app --reload
   ```
   *(On startup, FastAPI automatically launches a background Streamlit process on port `8501` for dashboard previews.)*

5. Open the interactive API documentation (Swagger UI):
   ```text
   http://127.0.0.1:8000/docs
   ```
   *(The **Authorize** button in Swagger UI is preconfigured and uses `/auth/token`.)*

6. Run unit tests (inside the activated `.venv`):
   ```bash
   python -B -m unittest discover -s tests -v
   ```

---

## 🏗 Architecture & Storage

### Data Flow

```text
Frontend (React + Recharts on browser canvas)
        ↓
Auth API (/auth/register, /auth/token) → JWT access_token
        ↓
Authorization: Bearer <token>
        ↓
Upload Dataset → POST /datasets/upload
        ↓
datasetId + fields + GET /datasets/{id}/preview (row sample for browser Recharts)
        ↓
UI Builder → Dashboard Schema v2 (JSON)
        ↓
        ├──────────────▶ POST /generate
        │                   ↓
        │            Pydantic Validation + Native Export Renderer
        │                   ↓
        │            ZIP (app.py + data/* + requirements.txt + run_local.bat/sh)
        │
        ├──────────────▶ /projects API (CRUD)
        │                   ↓
        │            project.json (storage/projects/<userId>/<projectId>)
        │
        └──────────────▶ /preview API
                            ↓
                     Live preview on Streamlit engine (port 8501)
```

### Schema Compilation Pipeline

```text
Editor state (Frontend)
        ↓
Dashboard Schema v2 (JSON)
        ↓
Pydantic Validation (app/schemas/dashboard.py)
        ↓
Backend Renderers (app/services/renderers/) & Utils (app/utils/)
        ↓
 ├── render_core.py    → shared rendering core (12-col CSS Grid + Vega-Lite)
 ├── export_render.py  → packages standalone app.py for ZIP archive
 └── preview_render.py → renders live dashboard preview on Streamlit (port 8501)
```

The client never submits executable Python code — only the declarative **Dashboard Schema v2** JSON, which undergoes strict backend validation before being compiled into safe Streamlit code.

### Authentication, CORS, and User Isolation

* **JWT Authentication:** **OAuth2 Password Bearer** (`HS256`, 7-day token lifetime). The token is passed via the `Authorization: Bearer <token>` header; missing or invalid tokens return `401 Unauthorized` (`{"detail": "Could not validate credentials"}`).
* **CORS:** [`app/main.py`](app/main.py) enables permissive `allow_origins=["*"]` for straightforward local and Docker setups (restricting allowed origins is recommended for public production deployments).
* **Isolation by `userId`:** all services (`dataset_service`, `project_service`, `preview_service`, `generate_routes`) read `current_user.id` from the JWT token:
  * users can only see their own projects and datasets;
  * datasets belonging to another user cannot be fetched, deleted, or used in code generation;
  * updating or deleting a Streamlit preview session is restricted to its owner.

### User Storage

Users are stored in a local JSON file `storage/users/users.json` (keyed by `userId`):

```json
{
  "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378": {
    "id": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
    "email": "test@example.com",
    "name": "Alex",
    "passwordHash": "$argon2id$v=19$m=65536,t=3,p=4$...",
    "createdAt": "2026-10-10T12:00:00+00:00",
    "disabled": false
  }
}
```

Passwords are hashed with **Argon2** (`pwdlib[argon2]`) using constant-time verification against timing attacks for non-existent users.

### Dataset and Project Storage

#### Datasets

```text
storage/datasets/<userId>/<datasetId>/
  <name>.<ext>
  meta.json
```

* `<name>.<ext>` — uploaded data file (saved under the dataset's name).
* `meta.json` — dataset metadata: `datasetId`, `userId`, file name (`name`), `format`, `delimiter`, `encoding`, workbook sheet (`sheetName`), column list (`fields`), column types (`fieldTypes`), size in bytes (`size`), and `createdAt`.

#### Projects

```text
storage/projects/<userId>/<projectId>/
  project.json
```

Example `project.json`:

```json
{
  "id": "uuid",
  "userId": "uuid",
  "title": "Sales dashboard",
  "description": "Regional sales analysis",
  "previewImage": "data:image/jpeg;base64,...",
  "datasets": [
    {
      "datasetId": "uuid",
      "name": "sales.csv",
      "fields": ["date", "sales", "region"]
    }
  ],
  "editorState": {
    "components": [],
    "previewImage": "data:image/jpeg;base64,..."
  },
  "schema": {
    "version": 2,
    "dashboard": {
      "title": "Sales dashboard",
      "grid": { "columns": 12 }
    },
    "pages": [
      { "id": "page-main", "title": "Main", "order": 1 }
    ],
    "dataSources": [
      {
        "type": "backend_dataset",
        "datasetId": "uuid",
        "name": "sales.csv",
        "format": "csv",
        "delimiter": ",",
        "encoding": "utf-8",
        "sheetName": null,
        "fields": ["date", "sales", "region"]
      }
    ],
    "filters": [
      {
        "id": "filter-1",
        "type": "selectbox",
        "datasetId": "uuid",
        "pageId": "page-main",
        "order": 1,
        "layout": { "x": 0, "y": 0, "width": 4, "height": 100 },
        "title": "Region",
        "field": "region",
        "scope": "global",
        "widget": "selectbox"
      },
      {
        "id": "filter-2",
        "type": "data_control",
        "datasetId": "uuid",
        "pageId": "page-main",
        "order": 2,
        "layout": { "x": 4, "y": 0, "width": 4, "height": 100 },
        "title": "Sales range",
        "field": "sales",
        "scope": "global",
        "controlType": "range"
      }
    ],
    "views": [
      {
        "id": "view-1",
        "type": "metric",
        "datasetId": "uuid",
        "pageId": "page-main",
        "order": 3,
        "layout": { "x": 8, "y": 0, "width": 4, "height": 100 },
        "title": "Total sales",
        "field": "sales",
        "aggregation": "sum"
      },
      {
        "id": "view-2",
        "type": "bar_chart",
        "datasetId": "uuid",
        "pageId": "page-main",
        "order": 4,
        "layout": { "x": 0, "y": 120, "width": 12, "height": 320 },
        "title": "Sales by date",
        "x": "date",
        "y": "sales",
        "aggregation": "sum",
        "sort": "asc",
        "sortBy": "x"
      }
    ]
  },
  "createdAt": "2026-10-10T12:00:00",
  "updatedAt": "2026-10-10T12:30:00"
}
```

---

## 📡 API Endpoints

All protected endpoints require an `Authorization: Bearer <token>` header (missing or invalid tokens return `401 Unauthorized`).

| Method | Path | Auth | Description |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | — | Register a new user |
| `POST` | `/auth/token` | — | Obtain a JWT token (`OAuth2PasswordRequestForm`) |
| `GET` | `/auth/me` | `Bearer` | Get current user profile |
| `PUT` | `/auth/password` | `Bearer` | Change password |
| `POST` | `/datasets/upload` | `Bearer` | Upload CSV/TSV/Excel and save metadata |
| `GET` | `/datasets/{datasetId}` | `Bearer` | Get dataset metadata |
| `GET` | `/datasets/{datasetId}/preview` | `Bearer` | Sample rows (up to `10000`) for Recharts canvas |
| `DELETE` | `/datasets/{datasetId}` | `Bearer` | Delete dataset |
| `POST` | `/datasets/inspect-sheets` | `Bearer` | List Excel workbook sheets without saving |
| `GET` | `/projects` | `Bearer` | List user projects |
| `POST` | `/projects` | `Bearer` | Create project |
| `GET` | `/projects/{projectId}` | `Bearer` | Get full project object |
| `PUT` | `/projects/{projectId}` | `Bearer` | Partially or fully update project |
| `DELETE` | `/projects/{projectId}` | `Bearer` | Delete project |
| `POST` | `/generate` | `Bearer` | Validate schema and export ZIP archive |
| `POST` | `/preview` | `Bearer` | Create Streamlit preview session |
| `PUT` | `/preview/{sessionId}` | `Bearer` | Update schema in preview session |
| `GET` | `/preview/{sessionId}` | — | Internal endpoint for `preview_render.py` |
| `DELETE` | `/preview/{sessionId}` | `Bearer` | Delete preview session |

---

### 🔐 Auth API

#### 🔹 POST `/auth/register`

Registers a new user. The `name` field is optional.

##### Request (`application/json`)

```json
{
  "email": "test@example.com",
  "password": "123456",
  "name": "Alex"
}
```

##### Response `200`

```json
{
  "id": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
  "email": "test@example.com",
  "name": "Alex",
  "createdAt": "2026-10-10T12:00:00+00:00",
  "disabled": false
}
```

##### Possible Errors (`400`)

```json
{ "detail": "User already exists" }
```
```json
{ "detail": "Password must contain at least 6 characters" }
```

---

#### 🔹 POST `/auth/token`

Authenticates a user via `OAuth2PasswordRequestForm` and returns a JWT token.

##### Request (`application/x-www-form-urlencoded`)

```text
username=test@example.com&password=123456
```

##### Response `200`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

##### Possible Errors (`400`)

```json
{
  "detail": "Incorrect email or password"
}
```

---

#### 🔹 GET `/auth/me` *(Auth: Bearer)*

Returns the profile of the currently authenticated user.

##### Response `200`

```json
{
  "id": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
  "email": "test@example.com",
  "name": "Alex",
  "createdAt": "2026-10-10T12:00:00+00:00",
  "disabled": false
}
```

---

#### 🔹 PUT `/auth/password` *(Auth: Bearer)*

Changes the password of the currently authenticated user.

##### Request (`application/json`)

```json
{
  "currentPassword": "123456",
  "newPassword": "new_password_123"
}
```

##### Response `200`

```json
{
  "message": "Password changed successfully"
}
```

##### Possible Errors (`400`)

```json
{ "detail": "Current password is incorrect" }
```
```json
{ "detail": "Password must contain at least 6 characters" }
```

---

### 📁 Dataset API

#### 🔹 POST `/datasets/upload` *(Auth: Bearer)*

Uploads a data file (`.csv`, `.tsv`, `.xlsx`, `.xls`) to the server, validates its structure, and persists metadata (`meta.json`). Column types in `fieldTypes` are inferred automatically: `number`, `datetime`, `boolean`, `string`.

* **Content-Type:** `multipart/form-data`
* **Form fields:**
  * `dataset: File` (required) — dataset file
  * `name: string` (optional) — custom dataset name
  * `delimiter: string` (optional) — CSV/TSV delimiter (`auto`, `,`, `;`, `\t`, `|`)
  * `encoding: string` (optional) — CSV/TSV character encoding (e.g., `auto`, `utf-8`, `utf-8-sig`, `cp1251`)
  * `sheetName: string` (optional) — Excel sheet name

##### Response `200`

```json
{
  "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
  "userId": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
  "name": "sales.csv",
  "format": "csv",
  "delimiter": ",",
  "encoding": "utf-8",
  "sheetName": null,
  "fields": ["date", "region", "sales", "active"],
  "fieldTypes": {
    "date": "datetime",
    "region": "string",
    "sales": "number",
    "active": "boolean"
  },
  "size": 10240,
  "createdAt": "2026-10-10T12:00:00"
}
```

---

#### 🔹 GET `/datasets/{datasetId}` *(Auth: Bearer)*

Returns metadata for a previously uploaded dataset owned by the current user.

* **Response `200`:** metadata object (`datasetId`, `userId`, `name`, `format`, `delimiter`, `encoding`, `sheetName`, `fields`, `fieldTypes`, `size`, `createdAt`).
* **Response `404`:** `{"detail": "Dataset not found"}`.

---

#### 🔹 GET `/datasets/{datasetId}/preview?limit=10000` *(Auth: Bearer)*

Returns a bounded row sample and automatically inferred column types (`number`, `datetime`, `boolean`, `string`) for fast draft rendering of charts, tables, and metrics on the React editor canvas in the browser (**Recharts**). Unlike the Streamlit engine preview, this endpoint returns only a sample of up to `limit` rows.

* **Query parameters:** `limit` (default `10000`, allowed range `1..10000`).

##### Response `200`

```json
{
  "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
  "fields": ["date", "region", "sales", "active"],
  "fieldTypes": {
    "date": "datetime",
    "region": "string",
    "sales": "number",
    "active": "boolean"
  },
  "rows": [
    { "date": "2026-01-01", "region": "North", "sales": 120.5, "active": true }
  ],
  "returnedRows": 1,
  "limit": 10000
}
```

* **Possible errors:** `400` (file parsing error), `404` (`{"detail": "Dataset not found"}`).

---

#### 🔹 DELETE `/datasets/{datasetId}` *(Auth: Bearer)*

Deletes the current user's dataset folder (data file and `meta.json`).

* **Response `200`:** `{"deleted": true}`
* **Response `404`:** `{"detail": "Dataset not found"}`

---

#### 🔹 POST `/datasets/inspect-sheets` *(Auth: Bearer)*

Returns the list of sheet names from an uploaded Excel workbook (`.xlsx`, `.xls`) without saving the file to disk.

* **Content-Type:** `multipart/form-data` (form field `file: File`)
* **Response `200`:**
```json
{
  "sheets": ["Sheet1", "Sheet2"]
}
```
* **Response `400`:** `{"detail": "Файл не является книгой Excel (.xlsx, .xls)"}`

---

### 📂 Projects API

All projects are isolated by `userId`. When the `schema` field is provided, the backend automatically validates it against the **Dashboard Schema v2** contract (returning `422 Unprocessable Entity` on failure).

#### 🔹 GET `/projects` *(Auth: Bearer)*

Returns the user's project list (sorted by `updatedAt` descending) for the home gallery. `previewImage` contains a JPEG/PNG data URL for the canvas thumbnail; for legacy projects, the value is also read from `editorState.previewImage`.

##### Response `200`

```json
[
  {
    "id": "3f49e4c1-6a5a-4db2-b34a-c3b0b0f5d6f1",
    "title": "Sales dashboard",
    "description": "Department sales analysis",
    "datasetName": "sales.csv",
    "previewImage": "data:image/jpeg;base64,...",
    "createdAt": "2026-10-10T12:00:00",
    "updatedAt": "2026-10-10T12:30:00"
  }
]
```

---

#### 🔹 POST `/projects` *(Auth: Bearer)*

Creates a new project from an editor draft.

##### Request

```json
{
  "title": "Sales dashboard",
  "description": "Sales analysis",
  "datasets": [
    {
      "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
      "name": "sales.csv",
      "fields": ["date", "region", "sales"]
    }
  ],
  "editorState": {
    "components": [],
    "previewImage": "data:image/jpeg;base64,..."
  },
  "previewImage": "data:image/jpeg;base64,...",
  "schema": { "...": "Dashboard Schema v2 (see project.json example above)" }
}
```

---

#### 🔹 GET `/projects/{projectId}` *(Auth: Bearer)*

Returns the full project object (`id`, `userId`, `title`, `description`, `datasets`, `editorState`, `previewImage`, `schema`, `createdAt`, `updatedAt`) to restore the builder state when opening `/editor/:projectId`. The thumbnail is stored both at the top level and inside `editorState` for compatibility; JPEG/PNG data URLs up to 4 MiB decoded are accepted.

* **Response `404`:** `{"detail": "Project not found"}`

---

#### 🔹 PUT `/projects/{projectId}` *(Auth: Bearer)*

Partially or fully updates a project.
* If only `title` and/or `description` are sent from the home page (`ProjectsPage`), the backend updates only those fields and **preserves** the saved `datasets`, `editorState`, and `schema`.
* If a full project snapshot is sent from the editor (`EditorPage`), all fields are updated and `schema` is revalidated.

* **Possible errors:** `404` (`{"detail": "Project not found"}`), `422` (`schema` or `previewImage` validation error).

---

#### 🔹 DELETE `/projects/{projectId}` *(Auth: Bearer)*

Deletes the user's project from disk. Returns `{"deleted": true}`.

* **Response `404`:** `{"detail": "Project not found"}`

---

### ⚙️ Generate API

#### 🔹 POST `/generate` *(Auth: Bearer)*

Validates the **Dashboard Schema v2** payload and compiles a standalone Streamlit project into a ZIP archive. Data sources are read from `schema.dataSources` (each `datasetId` is verified for ownership by the current user).

##### Request

```json
{
  "schema": {
    "version": 2,
    "dashboard": {
      "title": "Sales dashboard",
      "grid": { "columns": 12 }
    },
    "pages": [
      { "id": "page-main", "title": "Main", "order": 1 }
    ],
    "dataSources": [
      {
        "type": "backend_dataset",
        "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
        "name": "sales.csv",
        "format": "csv",
        "delimiter": ",",
        "encoding": "utf-8",
        "sheetName": null,
        "fields": ["date", "region", "sales"]
      }
    ],
    "filters": [
      {
        "id": "filter-1",
        "type": "selectbox",
        "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
        "order": 1,
        "layout": { "x": 0, "y": 0, "width": 4, "height": 120 },
        "title": "Region",
        "field": "region",
        "scope": "global",
        "widget": "selectbox"
      }
    ],
    "views": [
      {
        "id": "chart-1",
        "type": "bar_chart",
        "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
        "order": 2,
        "layout": { "x": 4, "y": 0, "width": 8, "height": 360 },
        "title": "Sales by Date",
        "x": "date",
        "y": "sales",
        "aggregation": "sum",
        "sort": "asc",
        "sortBy": "y",
        "color": "#3b82f6",
        "colorMode": "gradient",
        "palette": ["#0ea5e9", "#3b82f6", "#6366f1", "#8b5cf6"]
      }
    ]
  }
}
```

##### Response `200` (`application/zip`)

Returns the `dashboard_project.zip` archive with the following layout:

```text
dashboard_project.zip
├── app.py              # Generated native Streamlit application (CSS Grid + Vega-Lite)
├── requirements.txt    # Python dependencies (streamlit, pandas, etc.)
├── README.md           # Local startup instructions
├── run_local.bat       # One-click launch script for Windows
├── run_local.sh        # One-click launch script for Linux / macOS
└── data/
    └── sales.csv       # Bound datasets from schema.dataSources
```

##### Possible Errors

* `400` — missing `schema`, empty `dataSources`, or missing `datasetId`.
* `404` — `{"detail": "Dataset not found"}` (dataset not found or belongs to another user).
* `422` — **Dashboard Schema v2** validation error.

---

### 👀 Streamlit Preview API (`/preview`)

Manages live preview sessions of the compiled dashboard on the actual **Streamlit** engine (`preview_render.py` on port `8501`; the default dark theme for the preview server is configured in [`.streamlit/config.toml`](.streamlit/config.toml)). Unlike the browser draft (which renders via **Recharts** on a sample from `/datasets/{id}/preview`), `/preview` uses the generated Python/Vega-Lite renderer against the full uploaded dataset.

#### 🔹 POST `/preview` *(Auth: Bearer)*

Creates a Streamlit preview session (validates `schema` and verifies ownership of every `datasetId` in `schema.dataSources`).

##### Request (`application/json`)

```json
{
  "schema": { "...": "Dashboard Schema v2" }
}
```

##### Response `200`

```json
{
  "sessionId": "7d9c2a1b-4c6e-4f0b-9f1a-2e3d4c5b6a7f",
  "previewUrl": "http://localhost:8501/?session_id=7d9c2a1b-4c6e-4f0b-9f1a-2e3d4c5b6a7f&revision=1&embed=true",
  "revision": 1,
  "expiresIn": 1800
}
```

* **Possible errors:** `400` (`dataSources are required`, `datasetId is required`, `Dataset '...' not found`), `422` (`schema` validation error).

---

#### 🔹 PUT `/preview/{sessionId}` *(Auth: Bearer)*

Updates the schema in an existing session, increments `revision`, and refreshes the TTL.

* **Request:** `{"schema": { ... }}`
* **Response `200`:** object with updated `previewUrl`, `revision`, and `expiresIn` (same format as `POST /preview`).
* **Possible errors:** `400` (session not found/expired or `dataSources`/`datasetId` error), `403` (`{"detail": "Preview belongs to another user"}`), `422` (`schema` validation error).

---

#### 🔹 GET `/preview/{sessionId}`

Internal endpoint for `preview_render.py` (no Bearer token required).

##### Response `200`

```json
{
  "schema": { "...": "Dashboard Schema v2" },
  "datasetsPaths": {
    "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f": "/app/storage/datasets/.../sales.csv"
  },
  "revision": 1,
  "updatedAt": "2026-10-10T12:30:00+00:00"
}
```

* **Response `404`:** `{"detail": "Preview not found or expired"}`

---

#### 🔹 DELETE `/preview/{sessionId}` *(Auth: Bearer)*

Explicitly deletes a session (inactive sessions are also automatically purged after TTL expiration).

* **Response `200`:** `{"deleted": true}`
* **Possible errors:** `403` (`{"detail": "Preview belongs to another user"}`), `404` (`{"detail": "Preview not found or expired"}`).

---

## 📄 Dashboard Schema v2 Contract

The complete schema specification, integrity rules, and all model fields are documented in [`DASHBOARD_SCHEMA_V2.md`](./DASHBOARD_SCHEMA_V2.md).

Contract summary:
* **13 component types:** filters (`selectbox`, `data_control`), Vega-Lite charts (`line_chart`, `bar_chart`, `area_chart`, `scatter_plot`), indicators (`metric`, `progress`), tables (`table` in `data` and `pivot` modes), text (`text`), navigation (`page_link`), and containers (`layout_group`, `tab_group`).
* **Layout & multi-page support:** 12-column grid (`x`, `y`, `width`, `height`), pages (`pages`, `pageId`), and nesting inside containers/tabs (`parentId`, `tabId`).
* **Data processing & styling:** aggregations (`none`, `sum`, `mean`, `count`, `min`, `max`), sorting (`sort`, `sortBy`), color modes (`solid`, `gradient`, `categorical` + `palette`), and card/axis options (`ComponentBase`, `axisLabel*`, `axisTitle*`).

---

## 🛠 Backend Internal Modules

```text
app/
├── api/
│   ├── auth_routes.py            → /auth/register, /auth/token, /auth/me, /auth/password
│   ├── datasets_routes.py        → /datasets/upload, /datasets/{id}, /datasets/{id}/preview, /datasets/inspect-sheets
│   ├── projects_routes.py        → CRUD /projects
│   ├── preview_routes.py         → CRUD /preview
│   └── generate_routes.py        → POST /generate (ZIP archive builder)
├── schemas/
│   └── dashboard.py              → Pydantic v2 models & Dashboard Schema v2 validation
├── utils/
│   ├── data_transform.py         → Pandas filtering, aggregations, sorting, and metric calculations
│   └── schema_utils.py           → schema helpers and string literal utilities
└── services/
    ├── auth_service.py           → JWT, Argon2 hashing, storage/users/users.json
    ├── dataset_service.py        → CSV/TSV/Excel saving, encoding & type inference, row sampling
    ├── project_service.py        → project storage in storage/projects/<userId>/<projectId>
    ├── preview_service.py        → Streamlit preview session management and TTL
    ├── preview_runtime_service.py→ background Streamlit process runner (port 8501)
    ├── generator_service.py      → code generator entry point
    └── renderers/
        ├── render_core.py        → shared dashboard rendering core (12-col CSS Grid + Vega-Lite)
        ├── export_render.py      → packages standalone app.py for ZIP archive
        └── preview_render.py     → Streamlit application for built-in dashboard preview
```

---

## ⚙️ Environment Variables

| Variable | Default | Description |
| --- | --- | --- |
| `SECRET_KEY` | built-in dev fallback | Secret key used to sign JWT tokens (set your own in production) |
| `PREVIEW_PORT` | `8501` | Port of the background Streamlit preview server |
| `PREVIEW_HOST` | `127.0.0.1` (`0.0.0.0` in Docker) | Host of the Streamlit preview server |
| `PREVIEW_PUBLIC_URL` | `http://localhost:8501` | Public URL used to build `previewUrl` |
| `PREVIEW_SESSION_TTL_SECONDS` | `1800` | Inactive preview session lifetime (30 min) |
| `STREAMLIT_BUILDER_API_BASE` | `http://localhost:8000` | FastAPI base URL used by `preview_render.py` |

---

## 🚧 Current Limitations (MVP) & Roadmap

The project is currently in MVP stage and is primarily intended for local usage, prototyping, and small teams.

### Current Limitations
* **File-based storage:** accounts, projects, and uploaded files are stored on disk (`storage/`, or `/app/storage` volume in Docker) without an external database or object storage.
* **No team collaboration or advanced auth:** projects belong to individual accounts — there is no real-time collaboration, role-based access control (RBAC), `refresh_token`, or password reset yet.
* **One dataset per component:** while a project supports multiple `dataSources`, joining tables (`JOIN`) or connecting directly to external databases and APIs is not supported yet.
* **Basic chart set & no server-side extensions:** pie charts (`pie_chart`) and custom theme builders for exported Streamlit apps are not supported yet; the **Extensions** page in the frontend is currently a showcase demo and does not inject third-party libraries into exported code.
* **Shared Streamlit preview process:** live preview runs on a single background Streamlit process (port `8501`) with in-memory TTL sessions — well suited for individual work or small teams, but not designed for high concurrent load.

### Roadmap
* **External database & object storage:** migrating users and projects to a relational database (PostgreSQL) and uploaded datasets to object storage (S3/MinIO) instead of the local `storage/` directory.
* **Extended auth & team collaboration:** adding `refresh_token`, password reset, role-based access control (RBAC), and collaborative project editing.
* **Expanded Streamlit charts & widgets:** adding new chart types (`pie_chart`) and additional interactive widgets to the schema and code generator.
* **Richer per-chart configuration:** expanding chart-specific properties (additional axis settings, legends, data labels, and visual styling).
* **Full extensions & custom themes support:** server-side persistence of enabled plugins, injecting third-party libraries (charts, maps, custom components) into generated `app.py`, and custom theme configuration for exported apps.
* **New data sources & joins:** direct connections to external databases/APIs and joining multiple datasets (`JOIN`) within a dashboard.
* **Versioning, code editor & publishing:** versioning saved dashboard schemas, built-in `app.py` preview/editing before export, and direct export or publishing of dashboards to a Git repository.

---

## 📄 License

Copyright © 2026 Project Authors and Contributors ([Contributors](https://github.com/AlexFeed/streamlit_project_backend/graphs/contributors))

The backend service source code is licensed under the **GNU Affero General Public License v3.0 (`AGPL-3.0-only`)** — see the [`LICENSE`](LICENSE) file for the full text.

* **For service users:** you may freely use, run, copy, and modify the platform, including inside organizations and to build commercial dashboards. If you modify the backend itself and distribute it or make it available over a network (e.g., as a web service or API), your version must also be released under `GNU AGPLv3` with copyright notices preserved.
* **Generated Dashboard Exception (Additional Permission, Section 7 AGPLv3):** the `GNU AGPLv3` terms apply **only to the builder's and backend's own source code**. Exported dashboards (`app.py` and the contents of the downloaded ZIP archive) are **not** subject to `AGPLv3` copyleft requirements — you are free to run, modify, sell, and embed them into any Python or Streamlit project (including closed-source and commercial applications) without opening your own code.
