from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router

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