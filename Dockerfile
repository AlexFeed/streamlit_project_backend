FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PREVIEW_HOST=0.0.0.0 \
    PREVIEW_PORT=8501

WORKDIR /app

# Install Python dependencies first to leverage Docker layer caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source and Streamlit theme configuration
COPY app ./app
COPY .streamlit ./.streamlit

RUN mkdir -p /app/storage

EXPOSE 8000 8501

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
