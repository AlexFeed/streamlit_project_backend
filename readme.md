# Streamlit Dashboard Generator API

Backend-сервис для генерации Streamlit-приложений на основе визуально собранной схемы дашборда, работает совместно с frontend сервисом https://github.com/AlexFeed/streamlit_project.

---

## 📌 Описание

Сервис позволяет:

1. Загрузить CSV-файл на backend
2. Получить metadata (названия колонок)
3. Использовать эти данные в визуальном конструкторе
4. Сгенерировать готовый Streamlit-проект (.zip)

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
 POST /generate
        ↓
 ZIP (app.py + data.csv)
```

---

## 📁 Хранение файлов (локально)

Датасеты сохраняются в файловой системе:

```
storage/datasets/<datasetId>/
  data.csv
  meta.json
```

- `data.csv` — сам файл
- `meta.json` — metadata (колонки, имя, дата загрузки)

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

- `dataset` — CSV файл

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

#### Response:

```json
{
  "datasetId": "uuid",
  "name": "sales.csv",
  "fields": ["date", "sales", "region"]
}
```

---

### 🔹 DELETE `/datasets/{datasetId}`

Удаление датасета с backend.

#### Response:

```json
{
  "deleted": true
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

## ⚠️ Важно

- CSV хранится на backend локально
- datasetId используется для связи frontend ↔ backend
- после удаления датасета генерация станет невозможной
- backend не требует повторной загрузки CSV в Streamlit

---

## 🧩 Поддерживаемые компоненты

| Компонент   | Описание |
|------------|--------|
| selectbox  | Глобальный фильтр |
| line_chart | Линейный график |
| bar_chart  | Столбчатый график |
| metric     | Метрика |

---

## 🛠 Технологии

- FastAPI
- Pandas
- Uvicorn
- Streamlit (генерируемый код)

---

## 🔮 Планы развития

- Поддержка layout (columns, grid)
- Preview через Streamlit runtime
- Проекты (projectId)
- Хранение в S3 / Object Storage
- Авторизация пользователей
- Версионирование дашбордов

---

## 📄 Лицензия

MIT