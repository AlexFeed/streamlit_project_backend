from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.services.preview_runtime_service import preview_runtime_service

# Routes
from app.api.auth_routes import router as auth_router
from app.api.datasets_routes import router as datasets_router
from app.api.generate_routes import router as generate_router
from app.api.preview_routes import router as preview_router
from app.api.projects_routes import router as projects_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # При старте backend сразу в фоне запускается steramlit приложение
    preview_runtime_service.start()
    yield
    # При закрытии сервера закрывается stramlit процесс
    preview_runtime_service.stop()

app = FastAPI(title="Streamlit Generator API", lifespan=lifespan)

# CORS (важно для фронта)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Including routes
app.include_router(auth_router)
app.include_router(datasets_router)
app.include_router(projects_router)
app.include_router(preview_router)
app.include_router(generate_router)