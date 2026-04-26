# Streamlit Dashboard Generator API

Backend-сервис для генерации Streamlit-приложений на основе визуально собранной схемы дашборда, работает совместно с frontend сервисом https://github.com/AlexFeed/streamlit_project.

---

## 📌 Описание

Сервис позволяет:

1. Загрузить CSV-файл на backend
2. Получить metadata (названия колонок)
3. Использовать эти данные в визуальном конструкторе
4. Предпросмотреть дашборд (preview)
5. Сгенерировать готовый Streamlit-проект (.zip)

---

## 🏗 Архитектура

```
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
       └──────────────▶ POST /generate
                           ↓
                    ZIP (app.py + data.csv)
```

---

## 🧠 Основная идея проекта

Ключевая архитектурная концепция:

```
Editor state (frontend)
        ↓
Normalized JSON schema (contract)
        ↓
Backend renderers
        ↓
 ├── runtime preview (Streamlit)
 └── final code (app.py)
```

👉 Один и тот же `schema` используется для:

* preview (runtime исполнение)
* генерации итогового кода

---

## 📁 Структура файлов после скачивания

```
storage/datasets/<datasetId>/
  data.csv
  meta.json
```

* `data.csv` — CSV файл
* `meta.json` — metadata (колонки, имя, дата загрузки)

---

## 🚀 Быстрый старт

### 1. Клонирование

```bash
git clone https://github.com/AlexFeed/streamlit_project_backend.git
cd streamlit_project_backend
```

---

### 2. Виртуальное окружение

#### Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

#### Mac / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

---

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

---

### 4. Запуск сервера

```bash
uvicorn app.main:app --reload
```

---

### 5. Swagger документация

```
http://127.0.0.1:8000/docs
```

---

# 📡 API

---

## 📁 Работа с датасетами

---

### 🔹 POST `/datasets/upload`

Загрузка CSV-файла на backend.

#### Request:

`multipart/form-data`

* `dataset` — CSV файл

#### Response:

```json
{
  "datasetId": "uuid",
  "name": "sales.csv",
  "storedName": "data.csv",
  "fields": ["date", "sales", "region"],
  "size": 10240,
  "createdAt": "2026-04-25T12:00:00"
}
```

---

### 🔹 GET `/datasets/{datasetId}`

Получение metadata датасета.

---

### 🔹 DELETE `/datasets/{datasetId}`

Удаление датасета с backend.

---

## 👀 Preview (предпросмотр)

---

### 🔹 POST `/preview`

Создаёт preview-сессию.

#### Request:

```json
{
  "schema": { ... },
  "datasetId": "uuid"
}
```

#### Response:

```json
{
  "sessionId": "uuid",
  "previewUrl": "http://localhost:8501/?session_id=uuid"
}
```

---

### 🔹 GET `/preview/{sessionId}`

Используется Streamlit runtime.

#### Response:

```json
{
  "schema": { ... },
  "datasetPath": "storage/datasets/<datasetId>/data.csv"
}
```

---

## ⚙️ Генерация проекта

---

### 🔹 POST `/generate`

Генерация Streamlit-проекта.

#### Request:

```json
{
  "schema": { ... },
  "datasetId": "uuid"
}
```

---

### 📤 Response

Возвращает `.zip` архив:

```
dashboard_project.zip
```

Содержимое:

```
app.py
data/
  sales.csv
requirements.txt
```

---

## ▶️ Как использовать результат

1. Распаковать архив
2. Установить зависимости:

```bash
pip install -r requirements.txt
```

3. Запустить:

```bash
streamlit run app.py
```

---

# 📄 JSON Schema (v1)

Frontend передаёт на backend нормализованную структуру:

```json
{
  "dashboard": {
    "title": "Untitled project"
  },
  "dataSource": {
    "datasetId": "uuid",
    "name": "sales.csv",
    "fields": ["date", "department", "sales"]
  },
  "filters": [
    {
      "type": "selectbox",
      "field": "department",
      "title": "Department",
      "order": 1,
      "scope": "global"
    }
  ],
  "views": [
    {
      "type": "line_chart",
      "x": "date",
      "y": "sales",
      "title": "Sales",
      "order": 2
    }
  ]
}
```

---

## ⚙️ Execution model (важно)

Текущий pipeline выполнения:

```
schema
  ↓
(в перспективе) execution plan
  ↓
runtime_render → Streamlit preview
code_render → app.py
```

👉 В будущем планируется выделение отдельного слоя `execution plan`,
чтобы избежать дублирования логики между runtime и code generation.

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

* preview-сессии хранятся в памяти (in-memory)
* поддерживается один dataset
* layout (grid) пока отсутствует
* ограниченный набор компонентов

---

## 🛠 Внутренние сервисы backend

```
dataset_service       → работа с CSV
preview_service       → хранение preview sessions
preview_runtime       → запуск Streamlit процесса
generator             → сборка app.py
renderers/            → runtime и code rendering
```

---

## 🧠 Важные архитектурные принципы

* schema — единый источник правды
* preview и generate используют одну и ту же модель данных
* backend не зависит от frontend состояния напрямую
* итоговый app.py полностью автономен

---

## 🧪 Dev notes

* preview использует отдельный Streamlit процесс (порт 8501)
* FastAPI и Streamlit работают независимо
* при использовании `--reload` возможны дубли процессов Streamlit
* рекомендуется в будущем перейти на lifecycle (lifespan)

---

## 🔮 Планы развития

* Валидация schema через Pydantic
* Execution plan (единая логика для renderers)
* Aggregations (mean, count, min, max)
* Layout (columns / grid)
* Расширение компонентов
* Кэширование preview
* Хранение проектов
* Облачное хранилище
