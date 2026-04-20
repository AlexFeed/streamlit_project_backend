from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from app.services.generator import generate_streamlit_code

router = APIRouter()

@router.post("/generate", response_class=PlainTextResponse)
async def generate_dashboard(schema: dict):
    code = generate_streamlit_code(schema)
    return code