# Streamlit Dashboard Generator API

Backend-сервис для генерации Streamlit-приложений на основе визуально собранной схемы дашборда, работает совместно с frontend сервисом https://github.com/AlexFeed/streamlit_project.

---

## 📌 Описание

Сервис позволяет:

1. Загрузить CSV-файл на backend
2. Получить metadata: `datasetId`, имя файла, список колонок
3. Использовать эти данные в визуальном конструкторе
4. Предпросмотреть дашборд через Streamlit preview runtime
5. Сгенерировать готовый Streamlit-проект `.zip`
6. Сохранять и управлять проектами дашбордов

---

## 🏗 Архитектура

```text
Frontend (React)
        ↓
 Upload CSV → /datasets/upload
        ↓
 datasetId + fields
        ↓
 UI Builder → JSON schema
        ↓
       ├──────────────▶ POST /preview
       │                   ↓
       │              Streamlit runtime
       │
       ├──────────────▶ POST /generate
       │                   ↓
       │            ZIP (app.py + data.csv)
       │
       └──────────────▶ /projects API
                           ↓
                   project.json (storage)
```

---

## 🧠 Основная идея проекта

```text
Editor state (frontend)
        ↓
Normalized JSON schema
        ↓
Backend renderers
        ↓
 ├── runtime preview
 └── final code generation
```

Один и тот же `schema` используется для:

* preview
* генерации итогового `app.py`

---

## 📁 Хранение данных

### Датасеты

```text
storage/datasets/<datasetId>/
  data.csv
  meta.json
```

### Проекты

```text
storage/projects/<projectId>/
  project.json
```

Пример `project.json`:

```json
{
  "id": "uuid",
  "title": "Sales dashboard",
  "description": "",
  "datasetMeta": {
    "datasetId": "uuid",
    "name": "sales.csv",
    "fields": ["date", "sales", "region"]
  },
  "editorState": {
    "components": []
  },
  "schema": {},
  "createdAt": "2026-04-27T12:00:00",
  "updatedAt": "2026-04-27T12:30:00"
}
```

---

## 🚀 Быстрый старт

### 1. Клонирование

```bash
git clone https://github.com/AlexFeed/streamlit_project_backend.git
cd streamlit_project_backend
```

### 2. Виртуальное окружение

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### Mac / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Запуск сервера

```bash
uvicorn app.main:app --reload
```

### 5. Swagger документация

```text
http://127.0.0.1:8000/docs
```

---

# 📡 API Endpoints

---

## 📁 Dataset API

---

## 🔹 POST `/datasets/upload`

Загружает CSV-файл на backend.

Используется страницей editor при загрузке датасета.

### Request

```text
Content-Type: multipart/form-data
```

Поле формы:

```text
dataset: File
```

Пример frontend-запроса:

```js
const formData = new FormData();
formData.append('dataset', file);

const response = await fetch('http://localhost:8000/datasets/upload', {
  method: 'POST',
  body: formData,
});

const datasetMeta = await response.json();
```

### Response `200`

```json
{
  "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
  "name": "sales.csv",
  "storedName": "data.csv",
  "fields": ["date", "department", "sales", "revenue"],
  "size": 10240,
  "createdAt": "2026-04-27T12:00:00"
}
```

### Где используется

```text
EditorPage
useDatasetState.handleFileUpload
```

---

## 🔹 GET `/datasets/{datasetId}`

Возвращает metadata ранее загруженного датасета.

### Request

```http
GET /datasets/9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f
```

### Response `200`

```json
{
  "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
  "name": "sales.csv",
  "storedName": "data.csv",
  "fields": ["date", "department", "sales", "revenue"],
  "size": 10240,
  "createdAt": "2026-04-27T12:00:00"
}
```

### Response `404`

```json
{
  "detail": "Dataset not found"
}
```

---

## 🔹 DELETE `/datasets/{datasetId}`

Удаляет CSV и `meta.json` с backend.

### Request

```http
DELETE /datasets/9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f
```

### Response `200`

```json
{
  "deleted": true
}
```

### Где используется

```text
EditorPage
useDatasetState.clearDataset
```

---

# 📂 Projects API

Projects API нужен для связи главной страницы проектов и editor.

---

## 🔹 GET `/projects`

Возвращает список проектов для главной страницы.

### Request

```http
GET /projects
```

### Response `200`

```json
[
  {
    "id": "3f49e4c1-6a5a-4db2-b34a-c3b0b0f5d6f1",
    "title": "Sales dashboard",
    "description": "Анализ продаж по отделам",
    "datasetName": "sales.csv",
    "createdAt": "2026-04-27T12:00:00",
    "updatedAt": "2026-04-27T12:30:00"
  },
  {
    "id": "8c1c1f0d-4c7a-4bb0-92de-8f4f5df1a112",
    "title": "Untitled dashboard",
    "description": "",
    "datasetName": null,
    "createdAt": "2026-04-27T13:00:00",
    "updatedAt": "2026-04-27T13:00:00"
  }
]
```

### Frontend-пример

```js
const response = await fetch('http://localhost:8000/projects');
const projects = await response.json();
```

### Где используется

```text
ProjectsPage
```

---

## 🔹 POST `/projects`

Создаёт новый проект.

Есть два возможных сценария:

### Сценарий 1

Главная страница создаёт пустой проект и сразу открывает editor:

```text
ProjectsPage → POST /projects → navigate(`/editor/${project.id}`)
```

### Сценарий 2

Главная страница просто открывает `/editor`, а проект создаётся только после первого Save в editor:

```text
ProjectsPage → navigate('/editor')
EditorPage → Save project → POST /projects
```

Для текущей логики предпочтителен второй сценарий.

### Request

```json
{
  "title": "Новый проект",
  "description": "Описание проекта"
}
```

Также editor может отправить полный payload:

```json
{
  "title": "Sales dashboard",
  "description": "",
  "datasetMeta": {
    "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
    "name": "sales.csv",
    "fields": ["date", "sales", "region"]
  },
  "editorState": {
    "components": []
  },
  "schema": {}
}
```

### Response `200`

```json
{
  "id": "3f49e4c1-6a5a-4db2-b34a-c3b0b0f5d6f1",
  "title": "Sales dashboard",
  "description": "",
  "datasetMeta": {
    "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
    "name": "sales.csv",
    "fields": ["date", "sales", "region"]
  },
  "editorState": {
    "components": []
  },
  "schema": {},
  "createdAt": "2026-04-27T12:00:00",
  "updatedAt": "2026-04-27T12:00:00"
}
```

### Frontend-пример

```js
const response = await fetch('http://localhost:8000/projects', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    title: 'Новый проект',
    description: '',
  }),
});

const project = await response.json();
navigate(`/editor/${project.id}`);
```

---

## 🔹 GET `/projects/{projectId}`

Возвращает полный проект для восстановления editor.

### Request

```http
GET /projects/3f49e4c1-6a5a-4db2-b34a-c3b0b0f5d6f1
```

### Response `200`

```json
{
  "id": "3f49e4c1-6a5a-4db2-b34a-c3b0b0f5d6f1",
  "title": "Sales dashboard",
  "description": "Анализ продаж по отделам",
  "datasetMeta": {
    "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
    "name": "sales.csv",
    "fields": ["date", "department", "sales", "revenue"]
  },
  "editorState": {
    "components": [
      {
        "id": "line_chart-1714219200000-1",
        "type": "line_chart",
        "config": {
          "title": "Sales by date"
        },
        "bindings": {
          "xField": "date",
          "yField": "sales"
        }
      }
    ]
  },
  "schema": {
    "version": 1,
    "dashboard": {
      "title": "Untitled dashboard"
    },
    "dataSource": {
      "type": "backend_dataset",
      "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
      "name": "sales.csv",
      "fields": ["date", "department", "sales", "revenue"]
    },
    "filters": [],
    "views": [
      {
        "id": "line_chart-1714219200000-1",
        "type": "line_chart",
        "order": 1,
        "title": "Sales by date",
        "x": "date",
        "y": "sales"
      }
    ]
  },
  "createdAt": "2026-04-27T12:00:00",
  "updatedAt": "2026-04-27T12:30:00"
}
```

### Response `404`

```json
{
  "detail": "Project not found"
}
```

### Где используется

```text
EditorPage при открытии /editor/:projectId
```

---

## 🔹 PUT `/projects/{projectId}`

Обновляет проект.

Важно: endpoint работает как частичное обновление.

Если frontend отправляет только `title` и `description`, то backend не должен затирать:

* `datasetMeta`
* `editorState`
* `schema`

---

### Вариант 1: обновление title/description с главной страницы

#### Request

```json
{
  "title": "Новое название проекта",
  "description": "Новое описание проекта"
}
```

#### Response `200`

```json
{
  "id": "3f49e4c1-6a5a-4db2-b34a-c3b0b0f5d6f1",
  "title": "Новое название проекта",
  "description": "Новое описание проекта",
  "datasetMeta": {
    "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
    "name": "sales.csv",
    "fields": ["date", "department", "sales", "revenue"]
  },
  "editorState": {
    "components": []
  },
  "schema": {},
  "createdAt": "2026-04-27T12:00:00",
  "updatedAt": "2026-04-27T12:45:00"
}
```

### Frontend-пример

```js
await fetch(`http://localhost:8000/projects/${projectId}`, {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    title: newTitle,
    description: newDescription,
  }),
});
```

---

### Вариант 2: сохранение проекта из editor

#### Request

```json
{
  "title": "Sales dashboard",
  "description": "",
  "datasetMeta": {
    "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
    "name": "sales.csv",
    "fields": ["date", "department", "sales", "revenue"]
  },
  "editorState": {
    "components": [
      {
        "id": "metric-1714219200000-1",
        "type": "metric",
        "config": {
          "title": "Total Sales",
          "description": "Sum of sales"
        },
        "bindings": {
          "valueField": "sales"
        }
      }
    ]
  },
  "schema": {
    "version": 1,
    "dashboard": {
      "title": "Untitled dashboard"
    },
    "dataSource": {
      "type": "backend_dataset",
      "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
      "name": "sales.csv",
      "fields": ["date", "department", "sales", "revenue"]
    },
    "filters": [],
    "views": [
      {
        "id": "metric-1714219200000-1",
        "type": "metric",
        "order": 1,
        "title": "Total Sales",
        "description": "Sum of sales",
        "field": "sales",
        "aggregation": "sum"
      }
    ]
  }
}
```

#### Response `200`

Возвращает обновлённый проект:

```json
{
  "id": "3f49e4c1-6a5a-4db2-b34a-c3b0b0f5d6f1",
  "title": "Sales dashboard",
  "description": "",
  "datasetMeta": {
    "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
    "name": "sales.csv",
    "fields": ["date", "department", "sales", "revenue"]
  },
  "editorState": {
    "components": []
  },
  "schema": {},
  "createdAt": "2026-04-27T12:00:00",
  "updatedAt": "2026-04-27T12:50:00"
}
```

---

## 🔹 DELETE `/projects/{projectId}`

Удаляет проект из `storage/projects`.

### Request

```http
DELETE /projects/3f49e4c1-6a5a-4db2-b34a-c3b0b0f5d6f1
```

### Response `200`

```json
{
  "deleted": true
}
```

### Response `404`

```json
{
  "detail": "Project not found"
}
```

### Frontend-пример

```js
await fetch(`http://localhost:8000/projects/${projectId}`, {
  method: 'DELETE',
});
```

---

# 👀 Preview API

---

## 🔹 POST `/preview`

Создаёт preview-сессию.

### Request

```json
{
  "schema": {
    "version": 1,
    "dashboard": {
      "title": "Untitled dashboard"
    },
    "dataSource": {
      "type": "backend_dataset",
      "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
      "name": "sales.csv",
      "fields": ["date", "sales"]
    },
    "filters": [],
    "views": []
  },
  "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f"
}
```

### Response `200`

```json
{
  "sessionId": "d38e91f3-87f6-42ea-9d07-9285b7d2e4bc",
  "previewUrl": "http://localhost:8501/?session_id=d38e91f3-87f6-42ea-9d07-9285b7d2e4bc"
}
```

### Где используется

```text
EditorPage Preview button
PreviewModal iframe
```

---

## 🔹 GET `/preview/{sessionId}`

Внутренний endpoint для Streamlit preview runtime.

Frontend обычно не вызывает этот endpoint напрямую.

### Request

```http
GET /preview/d38e91f3-87f6-42ea-9d07-9285b7d2e4bc
```

### Response `200`

```json
{
  "schema": {
    "version": 1,
    "dashboard": {
      "title": "Untitled dashboard"
    },
    "dataSource": {
      "type": "backend_dataset",
      "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
      "name": "sales.csv",
      "fields": ["date", "sales"]
    },
    "filters": [],
    "views": []
  },
  "datasetPath": "storage/datasets/9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f/data.csv"
}
```

---

# ⚙️ Generate API

---

## 🔹 POST `/generate`

Генерирует автономный Streamlit-проект.

### Request

```json
{
  "schema": {
    "version": 1,
    "dashboard": {
      "title": "Untitled dashboard"
    },
    "dataSource": {
      "type": "backend_dataset",
      "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
      "name": "sales.csv",
      "fields": ["date", "department", "sales"]
    },
    "filters": [
      {
        "id": "selectbox-1",
        "type": "selectbox",
        "order": 1,
        "title": "Department",
        "field": "department",
        "scope": "global"
      }
    ],
    "views": [
      {
        "id": "line-chart-1",
        "type": "line_chart",
        "order": 2,
        "title": "Sales by Date",
        "x": "date",
        "y": "sales"
      }
    ]
  },
  "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f"
}
```

### Response `200`

```text
Content-Type: application/zip
```

Файл:

```text
dashboard_project.zip
```

Содержимое архива:

```text
app.py
requirements.txt
data/
  sales.csv
```

---

# 🔄 Frontend Flow

---

## Новый дашборд

```text
ProjectsPage → "Новый проект"
    ↓
navigate('/editor')
    ↓
EditorPage работает в draft mode
    ↓
localStorage сохраняет черновик
    ↓
Save project
    ↓
POST /projects
    ↓
localStorage draft очищается
    ↓
navigate('/editor/:projectId')
```

---

## Открытие существующего проекта

```text
ProjectsPage → клик по карточке
    ↓
navigate('/editor/:projectId')
    ↓
EditorPage делает GET /projects/{projectId}
    ↓
восстанавливаются:
  - components
  - datasetMeta
  - schema
```

---

## Обновление title/description на главной

```text
ProjectsPage → изменить title/description
    ↓
PUT /projects/{projectId}
    ↓
payload содержит только title/description
    ↓
backend не затирает editorState/schema/datasetMeta
```

---

# 📄 JSON Schema v1

```json
{
  "version": 1,
  "dashboard": {
    "title": "Untitled dashboard"
  },
  "dataSource": {
    "type": "backend_dataset",
    "datasetId": "uuid",
    "name": "sales.csv",
    "fields": ["date", "department", "sales"]
  },
  "filters": [
    {
      "id": "selectbox-1",
      "type": "selectbox",
      "order": 1,
      "title": "Department",
      "field": "department",
      "scope": "global"
    }
  ],
  "views": [
    {
      "id": "line-chart-1",
      "type": "line_chart",
      "order": 2,
      "title": "Sales by Date",
      "x": "date",
      "y": "sales"
    },
    {
      "id": "metric-1",
      "type": "metric",
      "order": 3,
      "title": "Total Sales",
      "description": "Sum of filtered sales",
      "field": "sales"
    }
  ]
}
```

---

## ⚙️ Execution model

```text
schema
  ↓
runtime_render → Streamlit preview
code_render → app.py
```

---

## 🧩 Поддерживаемые компоненты

| Компонент  | Описание          |
| ---------- | ----------------- |
| selectbox  | Глобальный фильтр |
| line_chart | Линейный график   |
| bar_chart  | Столбчатый график |
| metric     | Метрика           |

---

## ⚠️ Ограничения

* preview-сессии хранятся in-memory
* после перезапуска backend старые previewUrl перестают работать
* поддерживается один dataset
* layout/grid пока отсутствует
* авторизация пока не подключена
* БД пока не используется, проекты хранятся в файлах

---

## 🛠 Внутренние сервисы backend

```text
dataset_service       → работа с CSV
preview_service       → preview sessions
preview_runtime       → запуск Streamlit процесса
project_service       → хранение проектов
generator             → сборка app.py
renderers/            → runtime и code rendering
```

---

## 🧠 Важные архитектурные принципы

* schema — единый источник правды
* preview и generate используют одну и ту же schema
* backend не зависит от frontend state напрямую
* project.json хранит editorState для восстановления редактора
* итоговый app.py полностью автономен
* localStorage используется только для несохранённого draft `/editor`

---

## 🔮 Планы развития

* Валидация schema через Pydantic
* Execution plan
* Aggregations: mean, count, min, max
* Layout/grid
* База данных вместо файлового хранения
* Авторизация пользователей
* Версионирование проектов
* Облачное хранилище

