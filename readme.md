# Streamlit Dashboard Generator API

Backend-сервис для генерации Python-кода Streamlit-приложений на основе JSON-схемы, полученной из визуального конструктора.

---

## 📌 Описание

Этот сервис принимает описание дашборда (schema) и генерирует готовый `.py` файл со Streamlit-приложением.

Поддерживается MVP-функционал:

- 📊 Линейные графики (`line_chart`)
- 📊 Столбчатые графики (`bar_chart`)
- 🔢 Метрики (`metric`)
- 🔍 Глобальные фильтры (`selectbox`)
- 📁 Работа с локальным CSV

---

## 🏗 Архитектура

```
Frontend (React)
        ↓
   JSON schema
        ↓
Backend (FastAPI)
        ↓
Generated .py (Streamlit app)
```

---

## 🚀 Быстрый старт

### 1. Клонирование репозитория

```bash
git clone https://github.com/AlexFeed/streamlit_project_backend.git
cd streamlit_project_backend
```

---

### 2. Создание виртуального окружения

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

### 5. Документация API

После запуска доступна по адресу:

```
http://127.0.0.1:8000/docs
```

---

## 📡 API

### POST `/generate`

Генерирует Streamlit-код на основе schema.

---

### 📥 Request (JSON)

Пример:

```json
{
  "version": 1,
  "dashboard": {
    "title": "Sales Dashboard"
  },
  "dataSource": {
    "type": "local_csv",
    "name": "sales.csv",
    "fields": ["date", "sales", "department"]
  },
  "components": [
    {
      "id": "selectbox-1",
      "type": "selectbox",
      "order": 1,
      "config": {
        "title": "Выберите отдел"
      },
      "bindings": {
        "field": "department"
      }
    },
    {
      "id": "line_chart-1",
      "type": "line_chart",
      "order": 2,
      "config": {
        "title": "Продажи по датам"
      },
      "bindings": {
        "xField": "date",
        "yField": "sales"
      }
    }
  ]
}
```

---

### 📤 Response

Возвращает plain text:

```python
import streamlit as st
...
```

---

## ▶️ Как использовать результат

1. Сохраните полученный код как:

```
generated_dashboard.py
```

2. Поместите CSV файл рядом со скриптом:

```
generated_dashboard.py
sales.csv
```

3. Запустите:

```bash
streamlit run generated_dashboard.py
```

---

## ⚠️ Важно

- Имя CSV файла должно совпадать с `dataSource.name`
- CSV должен находиться в той же папке, что и `.py` файл
- Backend не хранит файлы — он только генерирует код

---

## 🧩 Поддерживаемые компоненты (MVP)

| Компонент   | Описание           |
|------------|--------------------|
| selectbox  | Глобальный фильтр  |
| line_chart | Линейный график    |
| bar_chart  | Столбчатый график  |
| metric     | Метрика (sum)      |

---

## 🛠 Технологии

- Python
- FastAPI
- Uvicorn
- Pandas
- Streamlit (в генерируемом коде)

---

## 🔮 Планы развития

- Поддержка дополнительных визуализаций
- Layout (columns, tabs)
- Загрузка CSV через frontend → backend
- Генерация `.zip` (код + данные)
- Валидация schema через Pydantic
- Переход на декларативную генерацию (templates / renderers)