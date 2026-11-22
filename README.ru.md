[English](README.md) | **Русский**

# Streamlit Dashboard Generator API (Backend)

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/python-3.14-blue.svg?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Pandas](https://img.shields.io/badge/pandas-%23150458.svg?style=for-the-badge&logo=pandas&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

Backend-сервис на базе **FastAPI** для конструктора дашбордов [`streamlit_project`](https://github.com/AlexFeed/streamlit_project). Отвечает за авторизацию, загрузку таблиц, хранение проектов, валидацию схемы **Dashboard Schema v2**, встроенный предпросмотр на **Streamlit** и сборку готового Python-проекта в ZIP-архив.

---

## 📌 Основные возможности

1. **Авторизация и аккаунты:** регистрация (с опциональным полем `name`), вход по **JWT (OAuth2 Bearer)** с хешированием паролей **Argon2** и смена пароля (`PUT /auth/password`).
2. **Работа с датасетами:** загрузка файлов `.csv`, `.tsv`, `.xlsx` и `.xls` с выбором разделителя, автоопределением и выбором кодировки (`encoding`), выбором листа Excel, а также автоопределением типов колонок (`number`, `datetime`, `boolean`, `string`).
3. **Данные для холста редактора:** быстрая выборка строк (`GET /datasets/{id}/preview`, до `10000` строк) для отрисовки графиков, таблиц и метрик в браузере через библиотеку **Recharts**.
4. **Валидация схемы дашборда:** строгая проверка **Dashboard Schema v2** через **Pydantic v2** — многостраничность (`pages`), несколько датасетов в одном проекте (`dataSources`), 12-колоночная сетка и 13 типов компонентов.
5. **Экспорт готового проекта:** генерация автономного Streamlit-приложения в ZIP-архиве (`app.py`, `data/*`, `requirements.txt`, `README.md`, `run_local.bat`, `run_local.sh`).
6. **Предпросмотр на Streamlit:** встроенный сервер **Streamlit** (порт `8501`) для проверки реального сгенерированного дашборда без скачивания архива (неактивные сессии автоматически очищаются по TTL).
7. **Хранение и изоляция данных:** сохранение проектов и датасетов на диске с полной изоляцией между пользователями.

---

## 🚀 Запуск сервиса

### Вариант 1. Запуск всей платформы через Docker

Запускать этот репозиторий отдельно в Docker обычно не нужно — вся платформа (веб-редактор, backend API и встроенный предпросмотр на Streamlit) поднимается одной командой.

Готовый Docker-образ backend-сервиса (`ghcr.io/alexfeed/streamlit_project_backend:latest`) подключается в общем файле [`docker-compose.yml`](https://github.com/AlexFeed/streamlit_project/blob/main/docker-compose.yml) в репозитории фронтенда [`streamlit_project`](https://github.com/AlexFeed/streamlit_project). Там же находится подробная пошаговая инструкция по запуску всего проекта через Docker.

**Что делает backend-контейнер в составе `docker-compose.yml`:**
* открывает порт `8000` (FastAPI REST API и Swagger UI) и порт `8501` (сервер предпросмотра на Streamlit);
* сохраняет аккаунты, проекты и загруженные файлы в общий Docker volume `/app/storage`.

При необходимости локальной отладки образа его можно собрать из [`Dockerfile`](Dockerfile):
```bash
docker build -t streamlit-builder-backend .
```

---

### Вариант 2. Локальный запуск из исходников (для разработки)

Подходит для разработчиков, которые хотят запускать и дорабатывать API, валидацию схемы или генератор Streamlit-кода локально.

> **Важно:** этот репозиторий отвечает только за серверную часть. Для работы с визуальным конструктором в браузере нужно параллельно запустить веб-редактор из репозитория [`streamlit_project`](https://github.com/AlexFeed/streamlit_project) (инструкция по запуску находится в его `README.md`).

**Требования:** Python **3.14** (та же версия используется в [`Dockerfile`](Dockerfile) и CI).

1. Клонируйте репозиторий и перейдите в папку проекта:
   ```bash
   git clone https://github.com/AlexFeed/streamlit_project_backend.git
   cd streamlit_project_backend
   ```
2. Создайте и активируйте виртуальное окружение:
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
3. Установите зависимости:
   ```bash
   pip install -r requirements.txt
   ```
4. Запустите сервер:
   ```bash
   uvicorn app.main:app --reload
   ```
   *(При старте FastAPI автоматически запускает на порту `8501` фоновый процесс Streamlit для предпросмотра дашбордов.)*

5. Откройте интерактивную документацию API (Swagger UI):
   ```text
   http://127.0.0.1:8000/docs
   ```
   *(Кнопка **Authorize** в Swagger UI настроена и работает через `/auth/token`.)*

6. Запуск автотестов (в активированном `.venv`):
   ```bash
   python -B -m unittest discover -s tests -v
   ```

---

## 🏗 Архитектура и хранение данных

### Поток данных

```text
Frontend (React + Recharts на холсте в браузере)
        ↓
Auth API (/auth/register, /auth/token) → JWT access_token
        ↓
Authorization: Bearer <token>
        ↓
Upload Dataset → POST /datasets/upload
        ↓
datasetId + fields + GET /datasets/{id}/preview (выборка строк для Recharts в браузере)
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
                     Предпросмотр на движке Streamlit (port 8501)
```

### Идея компиляции схемы

```text
Editor state (Frontend)
        ↓
Dashboard Schema v2 (JSON)
        ↓
Pydantic Validation (app/schemas/dashboard.py)
        ↓
Backend Renderers (app/services/renderers/) & Utils (app/utils/)
        ↓
 ├── render_core.py    → единое ядро отрисовки (CSS Grid 12 col + Vega-Lite)
 ├── export_render.py  → сборка автономного app.py для ZIP-архива
 └── preview_render.py → предпросмотр дашборда на движке Streamlit (порт 8501)
```

Клиент никогда не передаёт исполняемый Python-код — только декларативную JSON-схему **Dashboard Schema v2**, которая проходит строгую валидацию на бэкенде и компилируется в безопасный код Streamlit.

### Авторизация, CORS и изоляция пользователей

* **JWT-авторизация:** стандарт **OAuth2 Password Bearer** (`HS256`, срок жизни токена — 7 дней). Токен передаётся в заголовке `Authorization: Bearer <token>`; при его отсутствии или невалидности возвращается `401 Unauthorized` (`{"detail": "Could not validate credentials"}`).
* **CORS:** в [`app/main.py`](app/main.py) для упрощения локального и Docker-запуска включён открытый режим `allow_origins=["*"]` (для публичного production-развёртывания рекомендуется ограничить список доменов).
* **Изоляция по `userId`:** все сервисы (`dataset_service`, `project_service`, `preview_service`, `generate_routes`) берут `current_user.id` из JWT-токена:
  * пользователь видит только свои проекты и датасеты;
  * нельзя получить, удалить или использовать в генерации чужой `datasetId`;
  * обновление и удаление сессии предпросмотра на Streamlit доступно только её владельцу.

### Хранение пользователей

Пользователи хранятся в локальном JSON-файле `storage/users/users.json` (словарь по `userId`):

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

Пароли хешируются через **Argon2** (`pwdlib[argon2]`) с защитой от timing-атак при проверке несуществующих пользователей.

### Хранение датасетов и проектов

#### Датасеты

```text
storage/datasets/<userId>/<datasetId>/
  <name>.<ext>
  meta.json
```

* `<name>.<ext>` — загруженный файл данных (сохранённый под именем датасета).
* `meta.json` — метаданные датасета: `datasetId`, `userId`, имя файла (`name`), формат (`format`), разделитель (`delimiter`), кодировка (`encoding`), лист книги (`sheetName`), список колонок (`fields`), типы (`fieldTypes`), размер в байтах (`size`), `createdAt`.

#### Проекты

```text
storage/projects/<userId>/<projectId>/
  project.json
```

Пример `project.json`:

```json
{
  "id": "uuid",
  "userId": "uuid",
  "title": "Sales dashboard",
  "description": "Анализ продаж по регионам",
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
      { "id": "page-main", "title": "Главная", "order": 1 }
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
        "title": "Регион",
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
        "title": "Диапазон продаж",
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
        "title": "Общие продажи",
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
        "title": "Продажи по датам",
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

Все защищённые маршруты требуют заголовок `Authorization: Bearer <token>` (при отсутствии или невалидности токена возвращается `401 Unauthorized`).

| Метод | Путь | Авторизация | Краткое описание |
| --- | --- | --- | --- |
| `POST` | `/auth/register` | — | Регистрация пользователя |
| `POST` | `/auth/token` | — | Получение JWT-токена (`OAuth2PasswordRequestForm`) |
| `GET` | `/auth/me` | `Bearer` | Профиль текущего пользователя |
| `PUT` | `/auth/password` | `Bearer` | Смена пароля |
| `POST` | `/datasets/upload` | `Bearer` | Загрузка CSV/TSV/Excel и сохранение метаданных |
| `GET` | `/datasets/{datasetId}` | `Bearer` | Получение метаданных датасета |
| `GET` | `/datasets/{datasetId}/preview` | `Bearer` | Выборка строк (до `10000`) для холста Recharts |
| `DELETE` | `/datasets/{datasetId}` | `Bearer` | Удаление датасета |
| `POST` | `/datasets/inspect-sheets` | `Bearer` | Список листов Excel-книги без сохранения |
| `GET` | `/projects` | `Bearer` | Список проектов пользователя |
| `POST` | `/projects` | `Bearer` | Создание проекта |
| `GET` | `/projects/{projectId}` | `Bearer` | Полный объект проекта |
| `PUT` | `/projects/{projectId}` | `Bearer` | Частичное или полное обновление проекта |
| `DELETE` | `/projects/{projectId}` | `Bearer` | Удаление проекта |
| `POST` | `/generate` | `Bearer` | Валидация схемы и экспорт ZIP-архива |
| `POST` | `/preview` | `Bearer` | Создание сессии предпросмотра на Streamlit |
| `PUT` | `/preview/{sessionId}` | `Bearer` | Обновление схемы в сессии предпросмотра |
| `GET` | `/preview/{sessionId}` | — | Внутренний эндпоинт для `preview_render.py` |
| `DELETE` | `/preview/{sessionId}` | `Bearer` | Удаление сессии предпросмотра |

---

### 🔐 Auth API

#### 🔹 POST `/auth/register`

Регистрирует нового пользователя. Поле `name` опционально.

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

##### Возможные ошибки (`400`)

```json
{ "detail": "User already exists" }
```
```json
{ "detail": "Password must contain at least 6 characters" }
```

---

#### 🔹 POST `/auth/token`

Авторизует пользователя по стандарту `OAuth2PasswordRequestForm` и возвращает JWT-токен.

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

##### Возможные ошибки (`400`)

```json
{
  "detail": "Incorrect email or password"
}
```

---

#### 🔹 GET `/auth/me` *(Auth: Bearer)*

Возвращает профиль текущего авторизованного пользователя.

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

Меняет пароль текущего авторизованного пользователя.

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

##### Возможные ошибки (`400`)

```json
{ "detail": "Current password is incorrect" }
```
```json
{ "detail": "Password must contain at least 6 characters" }
```

---

### 📁 Dataset API

#### 🔹 POST `/datasets/upload` *(Auth: Bearer)*

Загружает файл данных (`.csv`, `.tsv`, `.xlsx`, `.xls`) на сервер, проверяет его структуру и сохраняет метаданные (`meta.json`). Типы колонок в `fieldTypes` определяются автоматически: `number`, `datetime`, `boolean`, `string`.

* **Content-Type:** `multipart/form-data`
* **Form-поля:**
  * `dataset: File` (обязательное) — файл датасета
  * `name: string` (опциональное) — пользовательское имя датасета
  * `delimiter: string` (опциональное) — разделитель для CSV/TSV (`auto`, `,`, `;`, `\t`, `|`)
  * `encoding: string` (опциональное) — кодировка для CSV/TSV (например, `auto`, `utf-8`, `utf-8-sig`, `cp1251`)
  * `sheetName: string` (опциональное) — название листа для Excel-файла

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

Возвращает метаданные ранее загруженного датасета текущего пользователя.

* **Response `200`:** объект метаданных (`datasetId`, `userId`, `name`, `format`, `delimiter`, `encoding`, `sheetName`, `fields`, `fieldTypes`, `size`, `createdAt`).
* **Response `404`:** `{"detail": "Dataset not found"}`.

---

#### 🔹 GET `/datasets/{datasetId}/preview?limit=10000` *(Auth: Bearer)*

Возвращает ограниченную выборку строк датасета и автоматически определённые типы колонок (`number`, `datetime`, `boolean`, `string`) для быстрой отрисовки черновика графиков, таблиц и метрик на холсте React-редактора в браузере (библиотека **Recharts**). В отличие от предпросмотра на движке Streamlit, здесь отдаётся только сэмпл до `limit` строк.

* **Query-параметры:** `limit` (по умолчанию `10000`, допустимый диапазон `1..10000`).

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

* **Возможные ошибки:** `400` (ошибка чтения файла), `404` (`{"detail": "Dataset not found"}`).

---

#### 🔹 DELETE `/datasets/{datasetId}` *(Auth: Bearer)*

Удаляет папку датасета (файл данных и `meta.json`) текущего пользователя.

* **Response `200`:** `{"deleted": true}`
* **Response `404`:** `{"detail": "Dataset not found"}`

---

#### 🔹 POST `/datasets/inspect-sheets` *(Auth: Bearer)*

Возвращает список листов из загруженной книги Excel (`.xlsx`, `.xls`) без сохранения файла на диск.

* **Content-Type:** `multipart/form-data` (поле формы `file: File`)
* **Response `200`:**
```json
{
  "sheets": ["Лист1", "Лист2"]
}
```
* **Response `400`:** `{"detail": "Файл не является книгой Excel (.xlsx, .xls)"}`

---

### 📂 Projects API

Все проекты изолированы по `userId`. При передаче поля `schema` бэкенд автоматически валидирует его по контракту **Dashboard Schema v2** (при ошибке возвращает `422 Unprocessable Entity`).

#### 🔹 GET `/projects` *(Auth: Bearer)*

Возвращает список проектов пользователя (отсортированный по `updatedAt` по убыванию) для главной страницы. Поле `previewImage` содержит JPEG/PNG data URL для превью холста; для старых проектов значение также читается из `editorState.previewImage`.

##### Response `200`

```json
[
  {
    "id": "3f49e4c1-6a5a-4db2-b34a-c3b0b0f5d6f1",
    "title": "Sales dashboard",
    "description": "Анализ продаж по отделам",
    "datasetName": "sales.csv",
    "previewImage": "data:image/jpeg;base64,...",
    "createdAt": "2026-10-10T12:00:00",
    "updatedAt": "2026-10-10T12:30:00"
  }
]
```

---

#### 🔹 POST `/projects` *(Auth: Bearer)*

Создаёт новый проект из черновика редактора.

##### Request

```json
{
  "title": "Sales dashboard",
  "description": "Анализ продаж",
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
  "schema": { "...": "Dashboard Schema v2 (см. формат в примере project.json выше)" }
}
```

---

#### 🔹 GET `/projects/{projectId}` *(Auth: Bearer)*

Возвращает полный объект проекта (`id`, `userId`, `title`, `description`, `datasets`, `editorState`, `previewImage`, `schema`, `createdAt`, `updatedAt`) для восстановления состояния конструктора при открытии `/editor/:projectId`. Превью находится на верхнем уровне и внутри `editorState` для совместимости; допускаются JPEG/PNG data URL до 4 MiB декодированного изображения.

* **Response `404`:** `{"detail": "Project not found"}`

---

#### 🔹 PUT `/projects/{projectId}` *(Auth: Bearer)*

Частично или полностью обновляет проект.
* Если с главной страницы (`ProjectsPage`) переданы только `title` и/или `description`, бэкенд обновляет только их и **не затирает** сохранённые `datasets`, `editorState` и `schema`.
* Если из редактора (`EditorPage`) передан полный снимок проекта, обновляются все поля и перевалидируется `schema`.

* **Возможные ошибки:** `404` (`{"detail": "Project not found"}`), `422` (ошибка валидации `schema` или `previewImage`).

---

#### 🔹 DELETE `/projects/{projectId}` *(Auth: Bearer)*

Удаляет проект пользователя с диска. Возвращает `{"deleted": true}`.

* **Response `404`:** `{"detail": "Project not found"}`

---

### ⚙️ Generate API

#### 🔹 POST `/generate` *(Auth: Bearer)*

Валидирует схему **Dashboard Schema v2** и компилирует автономный Streamlit-проект в ZIP-архив. Источники данных берутся из `schema.dataSources` (каждый `datasetId` проверяется на принадлежность текущему пользователю).

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
      { "id": "page-main", "title": "Главная", "order": 1 }
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

Возвращает архив `dashboard_project.zip` со следующей структурой:

```text
dashboard_project.zip
├── app.py              # Сгенерированное нативное Streamlit-приложение (CSS Grid + Vega-Lite)
├── requirements.txt    # Зависимости Python-приложения (streamlit, pandas и др.)
├── README.md           # Инструкция по локальному запуску
├── run_local.bat       # Скрипт запуска в один клик для Windows
├── run_local.sh        # Скрипт запуска в один клик для Linux / macOS
└── data/
    └── sales.csv       # Привязанные датасеты из schema.dataSources
```

##### Возможные ошибки

* `400` — отсутствует `schema`, пустой `dataSources` или не указан `datasetId`.
* `404` — `{"detail": "Dataset not found"}` (датасет не найден или принадлежит другому пользователю).
* `422` — ошибка валидации **Dashboard Schema v2**.

---

### 👀 Streamlit Preview API (`/preview`)

Управляет сессиями предпросмотра итогового дашборда на реальном движке **Streamlit** (`preview_render.py` на порту `8501`; дефолтная тёмная тема сервера предпросмотра задаётся в [`.streamlit/config.toml`](.streamlit/config.toml)). В отличие от черновика в браузере (который строится на **Recharts** по выборке из `/datasets/{id}/preview`), предпросмотр через `/preview` использует сгенерированный Python/Vega-Lite-рендерер и полный загруженный датасет.

#### 🔹 POST `/preview` *(Auth: Bearer)*

Создаёт сессию предпросмотра на Streamlit (валидирует `schema`, проверяет владение каждым `datasetId` из `schema.dataSources`).

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

* **Возможные ошибки:** `400` (`dataSources are required`, `datasetId is required`, `Dataset '...' not found`), `422` (ошибка валидации `schema`).

---

#### 🔹 PUT `/preview/{sessionId}` *(Auth: Bearer)*

Обновляет схему в существующей сессии, увеличивает `revision` и продлевает TTL.

* **Request:** `{"schema": { ... }}`
* **Response `200`:** объект с обновлёнными `previewUrl`, `revision` и `expiresIn` (формат как в `POST /preview`).
* **Возможные ошибки:** `400` (сессия не найдена/истекла или ошибка `dataSources`/`datasetId`), `403` (`{"detail": "Preview belongs to another user"}`), `422` (ошибка валидации `schema`).

---

#### 🔹 GET `/preview/{sessionId}`

Внутренний эндпоинт для `preview_render.py` (авторизация по Bearer-токену не требуется).

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

Явно удаляет сессию (неактивные сессии также очищаются автоматически по истечении TTL).

* **Response `200`:** `{"deleted": true}`
* **Возможные ошибки:** `403` (`{"detail": "Preview belongs to another user"}`), `404` (`{"detail": "Preview not found or expired"}`).

---

## 📄 Контракт Dashboard Schema v2

Подробное описание схемы, правил целостности и всех полей моделей зафиксировано в [`DASHBOARD_SCHEMA_V2.ru.md`](./DASHBOARD_SCHEMA_V2.ru.md).

Краткое резюме контракта:
* **13 типов компонентов:** фильтры (`selectbox`, `data_control`), графики на Vega-Lite (`line_chart`, `bar_chart`, `area_chart`, `scatter_plot`), показатели (`metric`, `progress`), таблицы (`table` в режимах `data` и `pivot`), текст (`text`), навигация (`page_link`) и контейнеры (`layout_group`, `tab_group`).
* **Раскладка и многостраничность:** 12-колоночная сетка (`x`, `y`, `width`, `height`), страницы (`pages`, `pageId`) и вложенность в контейнеры/вкладки (`parentId`, `tabId`).
* **Обработка данных и оформление:** агрегации (`none`, `sum`, `mean`, `count`, `min`, `max`), сортировка (`sort`, `sortBy`), цветовые режимы (`solid`, `gradient`, `categorical` + `palette`) и настройки карточек/осей (`ComponentBase`, `axisLabel*`, `axisTitle*`).

---

## 🛠 Внутренние модули бэкенда

```text
app/
├── api/
│   ├── auth_routes.py            → /auth/register, /auth/token, /auth/me, /auth/password
│   ├── datasets_routes.py        → /datasets/upload, /datasets/{id}, /datasets/{id}/preview, /datasets/inspect-sheets
│   ├── projects_routes.py        → CRUD /projects
│   ├── preview_routes.py         → CRUD /preview
│   └── generate_routes.py        → POST /generate (сборка ZIP-архива)
├── schemas/
│   └── dashboard.py              → Pydantic v2 модели и валидация Dashboard Schema v2
├── utils/
│   ├── data_transform.py         → фильтрация, агрегации, сортировка и расчёт метрик на Pandas
│   └── schema_utils.py           → утилиты работы со схемой и строковыми литералами
└── services/
    ├── auth_service.py           → JWT, Argon2 хеширование, storage/users/users.json
    ├── dataset_service.py        → сохранение CSV/TSV/Excel, автоопределение кодировки и типов, выборка строк
    ├── project_service.py        → хранение проектов в storage/projects/<userId>/<projectId>
    ├── preview_service.py        → управление сессиями Streamlit-предпросмотра и их TTL
    ├── preview_runtime_service.py→ фоновый запуск процесса Streamlit (порт 8501)
    ├── generator_service.py      → точка входа генератора кода
    └── renderers/
        ├── render_core.py        → единое ядро отрисовки дашборда (CSS Grid 12 col + Vega-Lite)
        ├── export_render.py      → упаковка кода в автономный app.py для ZIP-архива
        └── preview_render.py     → Streamlit-приложение для встроенного предпросмотра дашборда
```

---

## ⚙️ Переменные окружения (Environment)

| Переменная | Значение по умолчанию | Описание |
| --- | --- | --- |
| `SECRET_KEY` | built-in dev fallback | Секретный ключ для подписи JWT-токенов (в production рекомендуется задавать свой) |
| `PREVIEW_PORT` | `8501` | Порт фонового Streamlit-сервера предпросмотра |
| `PREVIEW_HOST` | `127.0.0.1` (`0.0.0.0` в Docker) | Хост Streamlit-сервера предпросмотра |
| `PREVIEW_PUBLIC_URL` | `http://localhost:8501` | Публичный URL для формирования `previewUrl` |
| `PREVIEW_SESSION_TTL_SECONDS` | `1800` | Время жизни неактивной сессии предпросмотра (30 мин) |
| `STREAMLIT_BUILDER_API_BASE` | `http://localhost:8000` | Адрес FastAPI для обращения из `preview_render.py` |

---

## 🚧 Текущие ограничения (MVP) и планы развития

Проект находится в стадии MVP и рассчитан в первую очередь на локальное использование, прототипирование и работу небольших команд.

### Текущие ограничения
* **Файловое хранилище:** аккаунты, проекты и загруженные файлы хранятся на диске (`storage/`, в Docker — volume `/app/storage`) без внешней базы данных и объектного хранилища.
* **Нет командного доступа и расширенной авторизации:** проекты привязаны к конкретному аккаунту — пока нет совместного редактирования, ролевой модели (RBAC), `refresh_token` и функции сброса пароля.
* **Один источник данных на компонент:** схема поддерживает несколько `dataSources` в одном проекте, но объединять таблицы между собой (`JOIN`) или подключаться напрямую к внешним БД и API пока нельзя.
* **Базовый набор визуализаций и отсутствие серверных расширений:** в схеме пока нет круговых диаграмм (`pie_chart`) и настройки собственных тем оформления итогового Streamlit-приложения; раздел «Расширения» во frontend носит демонстрационный характер и не подключает сторонние библиотеки в экспортируемый код.
* **Общий фоновый процесс для предпросмотра на Streamlit:** предпросмотр работает на одном фоновом процессе Streamlit (порт `8501`), а сессии хранятся в памяти с TTL — это подходит для личной работы или небольшой команды, но не рассчитано на высокую конкурентную нагрузку.

### Планы развития (Roadmap)
* **Переход на внешнее хранилище:** перенос пользователей и проектов в реляционную БД (PostgreSQL), а загруженных датасетов — в объектное хранилище (S3/MinIO) вместо локальной папки `storage/`.
* **Расширение авторизации и командный доступ:** добавление `refresh_token`, сброса пароля, ролевой модели доступа (RBAC) и совместного редактирования проектов.
* **Расширенная поддержка графиков и виджетов Streamlit:** добавление новых видов диаграмм (`pie_chart`) и дополнительных интерактивных виджетов в схему и генератор кода.
* **Более гибкая настройка графиков:** расширение параметров конкретных графиков (дополнительные настройки осей, легенд, подписей значений и оформления).
* **Полноценная поддержка расширений и тем оформления:** серверное сохранение подключённых плагинов, реальное добавление сторонних библиотек (графиков, карт, кастомных компонентов) в генерируемый `app.py` и настройка тем оформления экспортируемого приложения.
* **Новые источники и объединение данных:** прямое подключение к внешним БД/API и объединение нескольких датасетов (`JOIN`) внутри одного дашборда.
* **Версионирование, редактор кода и публикация:** версионирование сохранённых схем дашбордов, поддержка встроенного просмотра/редактирования `app.py` перед экспортом и прямой экспорт или публикация дашборда в Git-репозиторий.

---

## 📄 Лицензия

Copyright © 2026 Авторы и контрибьюторы проекта ([Contributors](https://github.com/AlexFeed/streamlit_project_backend/graphs/contributors))

Исходный код backend-сервиса распространяется под лицензией **GNU Affero General Public License v3.0 (`AGPL-3.0-only`)** — полный текст приведён в файле [`LICENSE`](LICENSE).

* **Для пользователей сервиса:** вы можете бесплатно использовать, запускать, копировать и дорабатывать платформу, в том числе внутри компаний и для создания коммерческих дашбордов. Если вы модифицируете сам backend и распространяете его или предоставляете к нему доступ по сети (например, как веб-сервис или API), ваша версия также должна быть открыта под лицензией `GNU AGPLv3` с сохранением указания авторства.
* **Исключение для сгенерированных дашбордов (Additional Permission, Section 7 AGPLv3):** условия `GNU AGPLv3` относятся **только к коду самого конструктора и его серверной части**. Экспортируемые дашборды (`app.py` и содержимое скачиваемого ZIP-архива) **не подпадают** под копилефт-требования `AGPLv3` — вы можете свободно запускать, изменять, продавать и встраивать их в любые (в том числе закрытые и коммерческие) Python- и Streamlit-проекты без необходимости открывать свой код.
