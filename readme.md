# Streamlit Dashboard Generator API (Backend)

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Python](https://img.shields.io/badge/python-3.11+-blue.svg?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=Streamlit&logoColor=white)
![Pandas](https://img.shields.io/badge/pandas-%23150458.svg?style=for-the-badge&logo=pandas&logoColor=white)

Backend-сервис на базе **FastAPI** для валидации декларативных схем дашбордов (**Dashboard Schema v2**), работы с пользовательскими датасетами и компиляции визуально собранных дашбордов в автономные **Streamlit**-приложения. Работает совместно с клиентским приложением: [https://github.com/AlexFeed/streamlit_project](https://github.com/AlexFeed/streamlit_project).

---

## 📌 Основные возможности

Сервис позволяет:

1. Регистрировать пользователей и авторизовывать их через **JWT (OAuth2 Bearer)** с хешированием паролей **Argon2**.
2. Загружать пользовательские датасеты (`.csv`, `.tsv`, `.xlsx`, `.xls`) с выбором разделителей и листов excel источника, а также автоматическим определением типов колонок (`number`, `datetime`, `string`).
3. Отдавать быструю выборку строк (`GET /datasets/{id}/preview`) для живой отрисовки графиков на холсте React-конструктора (**Live Canvas**).
4. Валидировать декларативную схему дашборда (**Dashboard Schema v2**) через **Pydantic v2** (12-колоночная сетка, координаты `x/y`, размеры `width/height`, агрегации, сортировки и цветовые палитры).
5. Генерировать готовый к запуску автономный Streamlit-проект в виде `.zip` архива (`app.py`, `data/*.csv`, `requirements.txt`, `README.md`, `run_local.bat`, `run_local.sh`).
6. Поддерживать фоновый Streamlit runtime для интерактивных preview-сессий с автоматической очисткой по TTL.
7. Сохранять и управлять проектами дашбордов с полной изоляцией данных по пользователям.

---

## 🚀 Быстрый старт

### 1. Клонирование

~~~bash
git clone https://github.com/AlexFeed/streamlit_project_backend.git
cd streamlit_project_backend
~~~

### 2. Виртуальное окружение

#### Windows (PowerShell / CMD)

~~~powershell
python -m venv venv
venv\Scripts\activate
~~~

#### macOS / Linux

~~~bash
python3 -m venv venv
source venv/bin/activate
~~~

### 3. Установка зависимостей

~~~bash
pip install -r requirements.txt
~~~

### 4. Запуск сервера

~~~bash
uvicorn app.main:app --reload
~~~

*(При старте FastAPI автоматически запускает фоновый процесс Streamlit для preview runtime на порту `8501`).*

### 5. Swagger документация

~~~text
http://127.0.0.1:8000/docs
~~~
*(Кнопка **Authorize** в Swagger UI полностью настроена и работает через `/auth/token`).*

### 6. Запуск автотестов

~~~powershell
$env:PYTHONDONTWRITEBYTECODE='1'
.\venv\Scripts\python.exe -B -m unittest discover -s tests -v
~~~

---

# 📡 API Endpoints

Все endpoint'ы, кроме `/auth/register`, `/auth/token` и внутреннего `GET /preview/{sessionId}`, требуют заголовок авторизации:

~~~http
Authorization: Bearer <token>
~~~

---

## 🏗 Архитектура

~~~text
Frontend (React + Live Canvas)
        ↓
Auth API (/auth/register, /auth/token) → JWT access_token
        ↓
Authorization: Bearer <token>
        ↓
Upload CSV → POST /datasets/upload
        ↓
datasetId + fields + GET /datasets/{id}/preview (выборка для Live Canvas)
        ↓
UI Builder → Dashboard Schema v2 (JSON)
        ↓
        ├──────────────▶ POST /generate
        │                   ↓
        │            Pydantic Validation + Native Export Renderer
        │                   ↓
        │            ZIP (app.py + data.csv + requirements.txt + run_local.bat/sh)
        │
        ├──────────────▶ /projects API (CRUD)
        │                   ↓
        │            project.json (storage/projects/<userId>/<projectId>)
        │
        └──────────────▶ /preview API
                            ↓
                     Streamlit preview runtime (port 8501)
~~~

---

## 🧠 Основная идея проекта

~~~text
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
 └── preview_render.py → live runtime preview на порту 8501
~~~

Клиент никогда не передаёт исполняемый Python-код — только декларативную JSON-схему **Dashboard Schema v2**, которая проходит строгую валидацию на бэкенде и компилируется в безопасный код Streamlit.

---

## 🔐 Авторизация

В бэкенде реализована JWT-авторизация по стандарту **OAuth2 Password Bearer** (`HS256`, срок жизни токена — 7 дней).

После получения токена через `POST /auth/token` бэкенд возвращает:

~~~json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
~~~

Frontend сохраняет токен и передаёт его во все защищённые endpoint'ы в заголовке:

~~~http
Authorization: Bearer <token>
~~~

Если токен не передан, истёк или невалиден, бэкенд возвращает `401 Unauthorized`:

~~~json
{
  "detail": "Could not validate credentials"
}
~~~

---

## 👤 Хранение пользователей

Пользователи хранятся локально в JSON-файле:

~~~text
storage/users/users.json
~~~

Структура файла (словарь по `userId`):

~~~json
{
  "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378": {
    "id": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
    "email": "test@example.com",
    "passwordHash": "$argon2id$v=19$m=65536,t=3,p=4$...",
    "createdAt": "2026-10-10T12:00:00+00:00",
    "disabled": false
  }
}
~~~

Пароли не хранятся в открытом виде — используется криптостойкое хеширование **Argon2** (`pwdlib[argon2]`) с защитой от timing-атак при проверке несуществующих пользователей.

---

## 📁 Хранение данных

Все пользовательские данные изолированы по `userId`.

### Датасеты

~~~text
storage/datasets/<userId>/<datasetId>/
  <name>.<ext>
  meta.json
~~~

* `<name>.<ext>` — физический файл данных (сохранённый под именем датасета)
* `meta.json` — паспорт источника данных: `datasetId`, `userId`, имя файла (`name`), формат (`format`), разделитель (`delimiter`), лист книги (`sheetName`), список колонок (`fields`), типы (`fieldTypes`), размер в байтах (`size`), `createdAt`

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
  "description": "Анализ продаж по регионам",
  "dataset": {
    "datasetId": "uuid",
    "name": "sales.csv",
    "fields": ["date", "sales", "region"]
  },
  "editorState": {
    "components": []
  },
  "schema": {
    "version": 2,
    "dashboard": {
      "title": "Sales dashboard",
      "grid": { "columns": 12 }
    },
    "dataSource": {
      "type": "backend_dataset",
      "datasetId": "uuid",
      "name": "sales.csv",
      "fields": ["date", "sales", "region"]
    },
    "filters": [],
    "views": []
  },
  "createdAt": "2026-10-10T12:00:00",
  "updatedAt": "2026-10-10T12:30:00"
}
~~~

---

## 🛡 Изоляция пользователей

Все сервисы (`dataset_service`, `project_service`, `preview_service`, `generate_routes`) используют `current_user.id`, извлечённый из JWT-токена:

~~~text
✔ пользователь видит только свои проекты
✔ пользователь видит только свои датасеты
✔ пользователь не может получить, удалить или использовать в генерации чужой датасет по его datasetId
✔ управление preview-сессией (обновление/удаление) доступно только её владельцу
~~~

---

# 🔐 Auth API

## 🔹 POST `/auth/register`

Регистрирует нового пользователя.

### Request (`application/json`)

~~~json
{
  "email": "test@example.com",
  "password": "123456"
}
~~~

### Response `200`

~~~json
{
  "id": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
  "email": "test@example.com",
  "createdAt": "2026-10-10T12:00:00+00:00",
  "disabled": false
}
~~~

### Возможные ошибки (`400`)

~~~json
{ "detail": "User already exists" }
~~~
~~~json
{ "detail": "Password must contain at least 6 characters" }
~~~

---

## 🔹 POST `/auth/token`

Авторизует пользователя по стандарту `OAuth2PasswordRequestForm` и возвращает JWT-токен.

### Request (`application/x-www-form-urlencoded`)

~~~text
username=test@example.com&password=123456
~~~

### Response `200`

~~~json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
~~~

### Возможные ошибки (`400`)

~~~json
{
  "detail": "Incorrect email or password"
}
~~~

---

## 🔹 GET `/auth/me`

Возвращает профиль текущего авторизованного пользователя.

### Headers

~~~http
Authorization: Bearer <token>
~~~

### Response `200`

~~~json
{
  "id": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
  "email": "test@example.com",
  "createdAt": "2026-10-10T12:00:00+00:00",
  "disabled": false
}
~~~

---

# 📁 Dataset API

## 🔹 POST `/datasets/upload`

Загружает файл данных (`.csv`, `.tsv`, `.xlsx`, `.xls`) на сервер, проверяет его читаемость и сохраняет паспорт источника данных.

* **Headers:** `Authorization: Bearer <token>`
* **Content-Type:** `multipart/form-data`
* **Form-поля:**
  * `dataset: File` (обязательное) — файл датасета
  * `name: string` (опциональное) — пользовательское имя датасета
  * `delimiter: string` (опциональное) — разделитель для CSV/TSV (`,` / `;` / `\t` / `|`)
  * `sheetName: string` (опциональное) — название листа для Excel-файла

### Response `200`

~~~json
{
  "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
  "userId": "4c01eccb-d8ef-4a2f-b2bf-46c9c5f57378",
  "name": "sales.csv",
  "format": "csv",
  "delimiter": ",",
  "sheetName": null,
  "fields": ["date", "region", "sales"],
  "fieldTypes": {
    "date": "datetime",
    "region": "string",
    "sales": "number"
  },
  "size": 10240,
  "createdAt": "2026-10-10T12:00:00"
}
~~~

---

## 🔹 GET `/datasets/{datasetId}`

Возвращает метаданные ранее загруженного датасета текущего пользователя.

* **Response `200`:** объект метаданных (`datasetId`, `name`, `fields`, `size`, `createdAt`).
* **Response `404`:** `{"detail": "Dataset not found"}`.

---

## 🔹 GET `/datasets/{datasetId}/preview?limit=500`

Возвращает ограниченную выборку строк датасета и автоматически определённые типы колонок (`number`, `datetime`, `string`) для мгновенной отрисовки графиков на **Live Canvas** в React-редакторе.

* **Query-параметры:** `limit` (по умолчанию `500`, допустимый диапазон `1..1000`).

### Response `200`

~~~json
{
  "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
  "name": "sales.csv",
  "fields": ["date", "region", "sales"],
  "fieldTypes": {
    "date": "datetime",
    "region": "string",
    "sales": "number"
  },
  "fieldTypes": {
    "date": "datetime",
    "region": "string",
    "sales": "number"
  },
  "rows": [
    { "date": "2026-01-01", "region": "North", "sales": 120.5 }
  ],
  "returnedRows": 1,
  "limit": 500
}
~~~

---

## 🔹 DELETE `/datasets/{datasetId}`

Удаляет папку датасета (`data.csv` и `meta.json`) текущего пользователя.

* **Response `200`:** `{"deleted": true}`

---

## 🔹 POST `/datasets/inspect-sheets`

Считывает и возвращает список названий листов из загруженной книги Excel (`.xlsx`, `.xls`) без сохранения файла на диск.

* **Headers:** `Authorization: Bearer <token>`
* **Content-Type:** `multipart/form-data` (поле формы `file: File`)
* **Response `200`:**
~~~json
{
  "sheets": ["Лист1", "Лист2"]
}
~~~
* **Response `400`:** `{"detail": "Файл не является книгой Excel (.xlsx, .xls)"}`

---

# 📂 Projects API

Все проекты изолированы по `userId`. При передаче поля `schema` бэкенд автоматически валидирует его по контракту **Dashboard Schema v2** (при ошибке возвращает `422 Unprocessable Entity`).

## 🔹 GET `/projects`

Возвращает список проектов пользователя (отсортированный по `updatedAt` по убыванию) для главной страницы.

### Response `200`

~~~json
[
  {
    "id": "3f49e4c1-6a5a-4db2-b34a-c3b0b0f5d6f1",
    "title": "Sales dashboard",
    "description": "Анализ продаж по отделам",
    "datasetName": "sales.csv",
    "createdAt": "2026-10-10T12:00:00",
    "updatedAt": "2026-10-10T12:30:00"
  }
]
~~~

---

## 🔹 POST `/projects`

Создаёт новый проект из черновика редактора.

### Request

~~~json
{
  "title": "Sales dashboard",
  "description": "Анализ продаж",
  "dataset": {
    "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
    "name": "sales.csv",
    "fields": ["date", "region", "sales"]
  },
  "editorState": {
    "components": []
  },
  "schema": {
    "version": 2,
    "dashboard": {
      "title": "Sales dashboard",
      "grid": { "columns": 12 }
    },
    "dataSource": {
      "type": "backend_dataset",
      "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
      "name": "sales.csv",
      "fields": ["date", "region", "sales"]
    },
    "filters": [],
    "views": []
  }
}
~~~

---

## 🔹 GET `/projects/{projectId}`

Возвращает полный объект проекта (`id`, `userId`, `title`, `description`, `dataset`, `editorState`, `schema`, `createdAt`, `updatedAt`) для восстановления состояния конструктора при открытии `/editor/:projectId`.

---

## 🔹 PUT `/projects/{projectId}`

Частично или полностью обновляет проект.
* Если с главной страницы (`ProjectsPage`) переданы только `title` и/или `description`, бэкенд обновляет только их и **не затирает** сохранённые `dataset`, `editorState` и `schema`.
* Если из редактора (`EditorPage`) передан полный снимок проекта, обновляются все поля и перевалидируется `schema`.

---

## 🔹 DELETE `/projects/{projectId}`

Удаляет проект пользователя с диска. Возвращает `{"deleted": true}`.

---

# ⚙️ Generate API

## 🔹 POST `/generate`

Валидирует схему **Dashboard Schema v2** и компилирует автономный Streamlit-проект в ZIP-архив.

### Request

~~~json
{
  "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
  "schema": {
    "version": 2,
    "dashboard": {
      "title": "Sales dashboard",
      "grid": { "columns": 12 }
    },
    "dataSource": {
      "type": "backend_dataset",
      "datasetId": "9b2e9f3a-2b4e-4c91-9e4f-1f2a3c4d5e6f",
      "name": "sales.csv",
      "fields": ["date", "region", "sales"]
    },
    "filters": [
      {
        "id": "filter-1",
        "type": "selectbox",
        "order": 1,
        "layout": { "x": 0, "y": 0, "width": 4, "height": 120 },
        "title": "Region",
        "field": "region",
        "scope": "global"
      }
    ],
    "views": [
      {
        "id": "chart-1",
        "type": "bar_chart",
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
~~~

### Response `200` (`application/zip`)

Возвращает архив `dashboard_project.zip` со следующей структурой:

~~~text
dashboard_project.zip
├── app.py              # Сгенерированное нативное Streamlit-приложение (CSS Grid + Vega-Lite)
├── requirements.txt    # Зависимости (streamlit>=1.57, pandas>=2.2)
├── README.md           # Инструкция по локальному запуску
├── run_local.bat       # Скрипт запуска в один клик для Windows
├── run_local.sh        # Скрипт запуска в один клик для Linux / macOS
└── data/
    └── sales.csv       # Привязанный датасет
~~~

---

# 👀 Preview API

Управляет сессиями интерактивного предпросмотра для встроенного Streamlit runtime (`preview_render.py`):

* `POST /preview` — создать preview-сессию (проверяет владение `datasetId`, валидирует `schema`, возвращает `sessionId`, `previewUrl`, `revision`).
* `PUT /preview/{sessionId}` — обновить схему в существующей сессии и увеличить `revision`.
* `GET /preview/{sessionId}` — внутренний endpoint для `preview_render.py` (возвращает `schema`, `datasetPath`, `revision`).
* `DELETE /preview/{sessionId}` — явно удалить сессию (неактивные сессии также очищаются автоматически по истечении TTL).

---

# 📄 Контракт Dashboard Schema v2

Подробное описание контракта также зафиксировано в файле [`DASHBOARD_SCHEMA_V2.md`](./DASHBOARD_SCHEMA_V2.md).

## Поддерживаемые компоненты

| `type` | Назначение | Streamlit / Vega-Lite рендеринг |
| --- | --- | --- |
| `selectbox` | Глобальный фильтр по полю | `st.selectbox` (с синхронизацией через `st.session_state`) |
| `line_chart` | Линейный график | `st.line_chart` / Vega-Lite с интерактивным hover |
| `bar_chart` | Столбчатая диаграмма | `st.bar_chart` / Vega-Lite (поддержка `solid`, `gradient`, `categorical`) |
| `area_chart` | Диаграмма с областями | `st.area_chart` / Vega-Lite с градиентной заливкой |
| `scatter_plot` | Точечная диаграмма | `st.scatter_chart` / Vega-Lite (поддержка `solid`, `gradient`, `categorical`) |
| `metric` | Карточка KPI-метрики | Кастомная карточка / `st.metric` (`sum`, `mean`, `count`, `min`, `max`) |

## Возможности раскладки и обработки данных

* **Свободная 12-колоночная сетка (`layout`):** каждый компонент хранит `width` (`1..12`), `height` (`120..720` px) и координаты `x` (`0..11`), `y` (`>=0`). В экспортируемом `app.py` раскладка точно воспроизводится через адаптивную 12-колоночную CSS Grid-сетку.
* **Агрегации (`aggregation`):** `none`, `sum`, `mean`, `count`, `min`, `max` (для метрик обязательна агрегация кроме `none`).
* **Сортировка (`sort` и `sortBy`):** `none`, `asc`, `desc` с выбором сортировки по оси `x` или по агрегированному значению `y`.
* **Цветовые режимы (`colorMode` и `palette`):**
    * `solid` — единый цвет серии `color` (`#RRGGBB`);
    * `gradient` — плавное окрашивание по величине `Y` на основе массива `palette` (от 2 до 8 HEX-цветов);
    * `categorical` — циклическое окрашивание категорий по палитре `palette`.

---

## 🛠 Внутренние модули бэкенда

~~~text
app/
├── api/
│   ├── auth_routes.py            → /auth/register, /auth/token, /auth/me
│   ├── datasets_routes.py        → /datasets/upload, /datasets/{id}, /datasets/{id}/preview
│   ├── projects_routes.py        → CRUD /projects
│   ├── preview_routes.py         → CRUD /preview
│   └── generate_routes.py        → POST /generate (сборка ZIP-архива)
├── schemas/
│   └── dashboard.py              → Pydantic v2 модели и валидация Dashboard Schema v2
├── utils/
│   ├── data_transform.py         → фильтрация, агрегации, сортировка и расчёт метрик на Pandas
│   └── schema_utils.py           → упаковка 12-колоночной сетки и нормализация координат
└── services/
    ├── auth_service.py           → JWT, Argon2 хеширование, storage/users/users.json
    ├── dataset_service.py        → сохранение CSV, определение типов полей и выборка строк
    ├── project_service.py        → хранение проектов в storage/projects/<userId>/<projectId>
    ├── preview_service.py        → управление preview-сессиями и их TTL
    ├── preview_runtime_service.py→ фоновый запуск процесса Streamlit
    ├── generator_service.py      → точка входа генератора кода
    └── renderers/
        ├── render_core.py        → единое ядро отрисовки дашборда (CSS Grid 12 col + Vega-Lite)
        ├── export_render.py      → упаковка кода в автономный app.py для ZIP-архива
        └── preview_render.py     → Streamlit-приложение фонового runtime preview
~~~

---

## ⚙️ Переменные окружения (Environment)

| Переменная | Значение по умолчанию | Описание |
| --- | --- | --- |
| `PREVIEW_PORT` | `8501` | Порт фонового Streamlit-сервера предпросмотра |
| `PREVIEW_HOST` | `127.0.0.1` | Хост Streamlit-сервера предпросмотра |
| `PREVIEW_PUBLIC_URL` | `http://localhost:8501` | Публичный URL для формирования `previewUrl` |
| `PREVIEW_SESSION_TTL_SECONDS` | `1800` | Время жизни неактивной сессии предпросмотра (30 мин) |
| `STREAMLIT_BUILDER_API_BASE` | `http://localhost:8000` | Адрес FastAPI для обращения из `preview_render.py` |

---

## 🔮 Планы развития (Roadmap)

* Переход с файлового хранилища (`storage/`) на реляционную БД (PostgreSQL) и объектное хранилище (S3/MinIO) для датасетов.
* Добавление `refresh_token` и ролевой модели доступа (RBAC / совместный доступ к проектам).
* Поддержка нескольких датасетов и их объединения (JOIN) внутри одного дашборда.
* Поддержка новых источников данных
* Экспорт сгенерированного дашборда сразу в гит
* Новые типы компонентов (круговые диаграммы `pie_chart`, таблицы `dataframe`, диапазонные фильтры дат `date_input` и слайдеры `slider`).
* Версионирование сохранённых схем дашбордов.