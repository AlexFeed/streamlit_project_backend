from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

from app.services.preview_runtime_service import preview_runtime_service

app = FastAPI(title="Streamlit Generator API")

# CORS (важно для фронта)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # потом ограничишь
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# При запуске сервера запускается streamlit приложение на фоне
@app.on_event("startup")
def startup_event():
    preview_runtime_service.start()

# При закрытии сервера закрывается streamlit
@app.on_event("shutdown")
def shutdown_event():
    preview_runtime_service.stop()