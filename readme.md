# Streamlit Dashboard Generator API

Backend-сервис для генерации Streamlit-приложений на основе визуально собранной схемы дашборда, работает совместно с frontend сервисом https://github.com/AlexFeed/streamlit_project.

---

## 📌 Описание

Сервис позволяет:

1. Зарегистрировать пользователя и авторизоваться через JWT
2. Загрузить CSV-файл на backend
3. Получить metadata: `datasetId`, имя файла, список колонок
4. Использовать эти данные в визуальном конструкторе
5. Предпросмотреть дашборд через Streamlit preview runtime
6. Сгенерировать готовый Streamlit-проект `.zip`
7. Сохранять и управлять проектами дашбордов
8. Изолировать проекты и датасеты по пользователям

---

## 🏗 Архитектура

~~~text
Frontend (React)
        ↓
Auth API → JWT accessToken
        ↓
Authorization: Bearer <token>
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
~~~

---

## 🧠 Основная идея проекта

~~~text
Editor state (frontend)
        ↓
Normalized JSON schema
        ↓
Backend renderers
        ↓
 ├── runtime preview
 └── final code generation
~~~

Один и тот же `schema` используется для:

* preview
* генерации итогового `app.py`

---

## 🔐 Авторизация

В backend добавлена JWT-авторизация.

После регистрации или логина backend возвращает:

~~~json
{
  "user": {
    "id": "uuid",
    "email": "test@example.com"
  },
  "accessToken": "jwt_token"
}
~~~

Frontend должен сохранять `accessToken` и передавать его во все защищённые endpoint'ы:

~~~http
Authorization: Bearer <token>
~~~

Если токен не передан или невалиден, backend возвращает:

~~~json
{
  "detail": "Authorization header is required"
}
~~~

или:

~~~json
{
  "detail": "Invalid or expired token"
}
~~~

---

## 👤 Хранение пользователей

Пользователи хранятся локально в JSON-файле:

~~~text
storage/users/users.json
~~~

Пример:

~~~json
[
  {
    "id": "uuid",
    "email": "test@example.com",
    "passwordHash": "$2b$12$..."
  }
]
~~~

Пароли не хранятся в открытом виде. Для хранения используется bcrypt-хеширование.

---

## 📁 Хранение данных

Данные изолированы по пользователям.

### Датасеты

~~~text
storage/datasets/<userId>/<datasetId>/
  data.csv
  meta.json
~~~

* `data.csv` — загруженный CSV-файл
* `meta.json` — metadata: имя файла, список колонок, размер, дата загрузки

### Проекты

~~~text
storage/projects/<userId>/<projectId>/
  project.json
~~~

Пример `project.json`:

~~~json
{
  "id": "uuid",
  "userId": "uuid",
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
~~~

---

## 🧠 Изоляция пользователей

Backend использует `current_user["id"]` при работе с проектами и датасетами.

Это означает:

~~~text
✔ пользователь видит только свои проекты
✔ пользователь видит только свои datasets
✔ пользователь не может получить чужой dataset по datasetId
✔ preview и generate работают только с dataset текущего пользователя
~~~

---

## 🚀 Быстрый старт

### 1. Клонирование

~~~bash
git clone https://github.com/AlexFeed/streamlit_project_backend.git
cd streamlit_project_backend
~~~

---

### 2. Виртуальное окружение

#### Windows

~~~bash
python -m venv venv
venv\Scripts\activate
~~~

#### Mac / Linux

~~~bash
python3 -m venv venv
source venv/bin/activate
~~~

---

### 3. Установка зависимостей

~~~bash
pip install -r requirements.txt
~~~

Если используется bcrypt/passlib для авторизации, в зависимостях должны быть:

~~~text
passlib[bcrypt]==1.7.4
bcrypt==4.0.1
python-jose[cryptography]
~~~

---

### 4. Запуск сервера

~~~bash
uvicorn app.main:app --reload
~~~

---

### 5. Swagger документация

~~~text
http://127.0.0.1:8000/docs
~~~

---

# 📡 API Endpoints

Все endpoint'ы, кроме `/auth/register` и `/auth/login`, требуют авторизацию:

~~~http
Authorization: Bearer <token>
~~~

---

# 🔐 Auth API

---

## 🔹 POST `/auth/register`

Регистрирует нового пользователя.

### Request

~~~json
{
  "email": "test@example.com",
  "password": "123456"
}
~~~

### Response `200`

~~~json
{
  "user": {
    "id": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
    "email": "test@example.com"
  },
  "accessToken": "jwt_token"
}
~~~

### Возможные ошибки

Если пользователь уже существует:

~~~json
{
  "detail": "User already exists"
}
~~~

Если пароль слишком короткий:

~~~json
{
  "detail": "Password must contain at least 6 characters"
}
~~~

### Где используется

~~~text
AuthPage
~~~

---

## 🔹 POST `/auth/login`

Авторизует пользователя и возвращает JWT-токен.

### Request

~~~json
{
  "email": "test@example.com",
  "password": "123456"
}
~~~

### Response `200`

~~~json
{
  "user": {
    "id": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
    "email": "test@example.com"
  },
  "accessToken": "jwt_token"
}
~~~

### Возможные ошибки

~~~json
{
  "detail": "Invalid email or password"
}
~~~

### Где используется

~~~text
AuthPage
~~~

---

## 🔹 GET `/auth/me`

Возвращает текущего пользователя по токену.

### Request

~~~http
GET /auth/me
Authorization: Bearer <token>
~~~

### Response `200`

~~~json
{
  "id": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
  "email": "test@example.com"
}
~~~

### Возможные ошибки

~~~json
{
  "detail": "Authorization header is required"
}
~~~

или:

~~~json
{
  "detail": "Invalid or expired token"
}
~~~

### Где используется

~~~text
ProtectedRoute
Frontend auth check
~~~

---

# 📁 Dataset API

---

## 🔹 POST `/datasets/upload`

Загружает CSV-файл на backend.

Используется страницей editor при загрузке датасета.

### Headers

~~~http
Authorization: Bearer <token>
~~~

### Request

~~~text
Content-Type: multipart/form-data
~~~

Поле формы:

~~~text
dataset: File
~~~

### Frontend-пример

~~~js
const formData = new FormData();
formData.append('dataset', file);

const response = await authFetch('/datasets/upload', {
  method: 'POST',
  body: formData,
});

const datasetMeta = await response.json();
~~~

### curl-пример для Git Bash / bash

~~~bash
curl -X POST "http://127.0.0.1:8000/datasets/upload" \
  -H "Authorization: Bearer <token>" \
  -F "dataset=@/c/Users/Пользователь/Desktop/test.csv"
~~~

### Response `200`

~~~json
{
  "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
  "userId": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
  "name": "sales.csv",
  "storedName": "data.csv",
  "fields": ["date", "department", "sales", "revenue"],
  "size": 10240,
  "createdAt": "2026-04-27T12:00:00"
}
~~~

### Side effect

Создаётся папка:

~~~text
storage/datasets/<userId>/<datasetId>/
  data.csv
  meta.json
~~~

### Где используется

~~~text
EditorPage
useDatasetState.handleFileUpload
~~~

---

## 🔹 GET `/datasets/{datasetId}`

Возвращает metadata ранее загруженного датасета.

Backend ищет dataset только внутри папки текущего пользователя.

### Headers

~~~http
Authorization: Bearer <token>
~~~

### Request

~~~http
GET /datasets/9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f
~~~

### Response `200`

~~~json
{
  "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
  "userId": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
  "name": "sales.csv",
  "storedName": "data.csv",
  "fields": ["date", "department", "sales", "revenue"],
  "size": 10240,
  "createdAt": "2026-04-27T12:00:00"
}
~~~

### Response `404`

Если dataset не существует или принадлежит другому пользователю:

~~~json
{
  "detail": "Dataset not found"
}
~~~

---

## 🔹 DELETE `/datasets/{datasetId}`

Удаляет CSV и `meta.json` с backend.

Удаление работает только для dataset текущего пользователя.

### Headers

~~~http
Authorization: Bearer <token>
~~~

### Request

~~~http
DELETE /datasets/9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f
~~~

### Response `200`

~~~json
{
  "deleted": true
}
~~~

### Response `404`

~~~json
{
  "detail": "Dataset not found"
}
~~~

### Где используется

~~~text
EditorPage
useDatasetState.clearDataset
~~~

---

# 📂 Projects API

Projects API нужен для связи главной страницы проектов и editor.

Все проекты изолированы по `userId`.

---

## 🔹 GET `/projects`

Возвращает список проектов текущего пользователя для главной страницы.

### Headers

~~~http
Authorization: Bearer <token>
~~~

### Request

~~~http
GET /projects
~~~

### Response `200`

~~~json
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
~~~

### Frontend-пример

~~~js
const response = await authFetch('/projects');
const projects = await response.json();
~~~

### Где используется

~~~text
ProjectsPage
~~~

---

## 🔹 POST `/projects`

Создаёт новый проект для текущего пользователя.

Есть два возможных сценария.

### Сценарий 1

Главная страница создаёт пустой проект и сразу открывает editor:

~~~text
ProjectsPage → POST /projects → navigate(`/editor/${project.id}`)
~~~

### Сценарий 2

Главная страница просто открывает `/editor`, а проект создаётся только после первого Save в editor:

~~~text
ProjectsPage → navigate('/editor')
EditorPage → Save project → POST /projects
~~~

Для текущей логики предпочтителен второй сценарий.

### Headers

~~~http
Authorization: Bearer <token>
~~~

### Request

Минимальный request:

~~~json
{
  "title": "Новый проект",
  "description": "Описание проекта"
}
~~~

Editor может отправить полный payload:

~~~json
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
~~~

### Response `200`

~~~json
{
  "id": "3f49e4c1-6a5a-4db2-b34a-c3b0b0f5d6f1",
  "userId": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
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
~~~

### Frontend-пример

~~~js
const response = await authFetch('/projects', {
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
~~~

---

## 🔹 GET `/projects/{projectId}`

Возвращает полный проект для восстановления editor.

Backend ищет проект только внутри папки текущего пользователя.

### Headers

~~~http
Authorization: Bearer <token>
~~~

### Request

~~~http
GET /projects/3f49e4c1-6a5a-4db2-b34a-c3b0b0f5d6f1
~~~

### Response `200`

~~~json
{
  "id": "3f49e4c1-6a5a-4db2-b34a-c3b0b0f5d6f1",
  "userId": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
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
~~~

### Response `404`

Если проект не существует или принадлежит другому пользователю:

~~~json
{
  "detail": "Project not found"
}
~~~

### Где используется

~~~text
EditorPage при открытии /editor/:projectId
~~~

---

## 🔹 PUT `/projects/{projectId}`

Обновляет проект.

Endpoint работает как частичное обновление.

Если frontend отправляет только `title` и `description`, backend не затирает:

* `datasetMeta`
* `editorState`
* `schema`

---

### Вариант 1: обновление title/description с главной страницы

#### Headers

~~~http
Authorization: Bearer <token>
~~~

#### Request

~~~json
{
  "title": "Новое название проекта",
  "description": "Новое описание проекта"
}
~~~

#### Response `200`

~~~json
{
  "id": "3f49e4c1-6a5a-4db2-b34a-c3b0b0f5d6f1",
  "userId": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
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
~~~

### Frontend-пример

~~~js
await authFetch(`/projects/${projectId}`, {
  method: 'PUT',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    title: newTitle,
    description: newDescription,
  }),
});
~~~

---

### Вариант 2: сохранение проекта из editor

#### Request

~~~json
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
~~~

#### Response `200`

Возвращает обновлённый проект.

---

## 🔹 DELETE `/projects/{projectId}`

Удаляет проект из `storage/projects/<userId>/<projectId>`.

### Headers

~~~http
Authorization: Bearer <token>
~~~

### Request

~~~http
DELETE /projects/3f49e4c1-6a5a-4db2-b34a-c3b0b0f5d6f1
~~~

### Response `200`

~~~json
{
  "deleted": true
}
~~~

### Response `404`

~~~json
{
  "detail": "Project not found"
}
~~~

### Frontend-пример

~~~js
await authFetch(`/projects/${projectId}`, {
  method: 'DELETE',
});
~~~

---

# 👀 Preview API

---

## 🔹 POST `/preview`

Создаёт preview-сессию.

Backend проверяет dataset внутри папки текущего пользователя.

### Headers

~~~http
Authorization: Bearer <token>
~~~

### Request

~~~json
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
~~~

### Response `200`

~~~json
{
  "sessionId": "d38e91f3-87f6-42ea-9d07-9285b7d2e4bc",
  "previewUrl": "http://localhost:8501/?session_id=d38e91f3-87f6-42ea-9d07-9285b7d2e4bc"
}
~~~

### Где используется

~~~text
EditorPage Preview button
PreviewModal iframe
~~~

---

## 🔹 GET `/preview/{sessionId}`

Внутренний endpoint для Streamlit preview runtime.

Frontend обычно не вызывает этот endpoint напрямую.

Этот endpoint может не требовать Authorization, потому что его вызывает `preview_app.py` по случайному `sessionId`.

### Request

~~~http
GET /preview/d38e91f3-87f6-42ea-9d07-9285b7d2e4bc
~~~

### Response `200`

~~~json
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
  "datasetPath": "storage/datasets/<userId>/<datasetId>/data.csv"
}
~~~

---

# ⚙️ Generate API

---

## 🔹 POST `/generate`

Генерирует автономный Streamlit-проект.

Backend проверяет dataset внутри папки текущего пользователя.

### Headers

~~~http
Authorization: Bearer <token>
~~~

### Request

~~~json
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
~~~

### Response `200`

~~~text
Content-Type: application/zip
~~~

Файл:

~~~text
dashboard_project.zip
~~~

Содержимое архива:

~~~text
app.py
requirements.txt
data/
  sales.csv
~~~

---

# ▶️ Как использовать сгенерированный проект

1. Распаковать архив
2. Установить зависимости:

~~~bash
pip install -r requirements.txt
~~~

3. Запустить:

~~~bash
streamlit run app.py
~~~

Важно:

~~~text
Сгенерированный app.py автономен и не зависит от FastAPI backend.
~~~

---

# 🔄 Frontend Flow

---

## Авторизация

~~~text
AuthPage
    ↓
POST /auth/login или POST /auth/register
    ↓
accessToken сохраняется в localStorage
    ↓
ProtectedRoute открывает доступ к приложению
~~~

---

## Новый дашборд

~~~text
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
~~~

---

## Открытие существующего проекта

~~~text
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
~~~

---

## Обновление title/description на главной

~~~text
ProjectsPage → изменить title/description
    ↓
PUT /projects/{projectId}
    ↓
payload содержит только title/description
    ↓
backend не затирает editorState/schema/datasetMeta
~~~

---

# 📄 JSON Schema v1

Frontend передаёт на backend нормализованную структуру:

~~~json
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
      "field": "sales",
      "aggregation": "sum"
    }
  ]
}
~~~

---

## ⚙️ Execution model

Текущий pipeline выполнения:

~~~text
schema
  ↓
runtime_render → Streamlit preview
code_render → app.py
~~~

В будущем планируется выделение отдельного слоя `execution plan`, чтобы избежать дублирования логики между runtime и code generation.

---

## 🧩 Поддерживаемые компоненты

| Компонент  | Описание          |
| ---------- | ----------------- |
| selectbox  | Глобальный фильтр |
| line_chart | Линейный график   |
| bar_chart  | Столбчатый график |
| metric     | Метрика           |

---

## 🛠 Внутренние сервисы backend

~~~text
auth_service          → регистрация, логин, JWT, получение текущего пользователя
dataset_service       → работа с CSV и storage/datasets/<userId>/<datasetId>
project_service       → хранение проектов в storage/projects/<userId>/<projectId>
preview_service       → preview sessions
preview_runtime       → запуск Streamlit процесса
generator             → сборка app.py
renderers/            → runtime и code rendering
~~~

---

## 🧠 Важные архитектурные принципы

* schema — единый источник правды
* preview и generate используют одну и ту же schema
* backend не зависит от frontend state напрямую
* project.json хранит editorState для восстановления редактора
* итоговый app.py полностью автономен
* localStorage используется только для несохранённого draft `/editor`
* backend stateless: пользователь определяется по JWT
* userId участвует во всех файловых операциях с проектами и датасетами
* безопасность доступа обеспечивается на backend, а не только на frontend

---

## ⚠️ Ограничения

* JWT используется без refresh tokens
* users хранятся в JSON, а не в БД
* preview-сессии хранятся in-memory
* после перезапуска backend старые previewUrl перестают работать
* поддерживается один dataset на dashboard
* layout/grid пока отсутствует
* ограниченный набор компонентов
* роли пользователей пока отсутствуют

---

## 🧪 Dev notes

* preview использует отдельный Streamlit процесс (порт 8501)
* FastAPI и Streamlit работают независимо
* при использовании `--reload` возможны дубли процессов Streamlit
* рекомендуется в будущем перейти на lifecycle (`lifespan`)
* для тестирования API можно использовать Swagger: `http://127.0.0.1:8000/docs`
* при тестировании через curl нужно передавать токен в формате `Authorization: Bearer <token>`

---

## 🔮 Планы развития

* Валидация schema через Pydantic
* Execution plan
* Aggregations: mean, count, min, max
* Layout/grid
* База данных вместо файлового хранения
* Refresh tokens
* Роли пользователей
* Версионирование проектов
* Облачное хранилище
* Расширение компонентов