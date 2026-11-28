from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Routes
from app.api.auth_routes import router as auth_router
from app.api.datasets_routes import router as datasets_router
from app.api.generate_routes import router as generate_router
from app.api.preview_routes import router as preview_router
from app.api.projects_routes import router as projects_router
from app.services.preview_runtime_service import preview_runtime_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the Streamlit app in the background right when the backend starts
    preview_runtime_service.start()
    yield
    # Stop the Streamlit process when the server shuts down
    preview_runtime_service.stop()


def _format_validation_error(error: dict[str, Any]) -> str:
    loc = [str(part) for part in error.get("loc", ()) if part != "body"]
    message = str(error.get("msg", "Invalid value")).removeprefix("Value error, ")
    return f"{'.'.join(loc)}: {message}" if loc else message


async def request_validation_exception_handler(
    _request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    raw_errors = exc.errors()
    messages = [_format_validation_error(error) for error in raw_errors]
    detail = "; ".join(messages[:3]) or "Validation error"
    if len(messages) > 3:
        detail = f"{detail} (+{len(messages) - 3} more)"

    # Keep only JSON-safe summary fields; raw ctx may contain ValueError instances.
    safe_errors = [
        {
            "loc": list(error.get("loc", ())),
            "msg": str(error.get("msg", "")).removeprefix("Value error, "),
            "type": str(error.get("type", "")),
        }
        for error in raw_errors
    ]
    return JSONResponse(
        status_code=422,
        content={"detail": detail, "errors": safe_errors},
    )


app = FastAPI(title="Streamlit Generator API", lifespan=lifespan)
app.add_exception_handler(
    RequestValidationError,
    request_validation_exception_handler,  # type: ignore[arg-type]
)

# CORS (important for the frontend)
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
