import io
import zipfile
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from app.schemas.dashboard import validate_dashboard_schema
from app.services import auth_service, dataset_service
from app.services.generator_service import generate_streamlit_code

router = APIRouter()

# ГЕНЕРАЦИЯ STREAMLIT КОДА
@router.post("/generate")
async def generate_dashboard(payload: dict, current_user: Annotated[
    auth_service.User,
    Depends(auth_service.get_current_active_user),
],):
    schema = payload.get("schema")
    dataset_id = payload.get("datasetId")

    if not schema:
        raise HTTPException(status_code=400, detail="Schema is required")

    if not dataset_id:
        raise HTTPException(status_code=400, detail="datasetId is required")

    dataset_path = dataset_service.get_dataset_path(
        current_user.id,
        dataset_id,
    )
    dataset_meta = dataset_service.get_dataset_meta(
        current_user.id,
        dataset_id,
    )

    if not dataset_path or not dataset_meta:
        raise HTTPException(status_code=404, detail="Dataset not found")

    try:
        validated_schema = validate_dashboard_schema(schema)
    except (ValidationError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error))

    code = generate_streamlit_code(validated_schema)

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr("app.py", code)
        zip_file.write(dataset_path, f"data/{dataset_meta['name']}")
        zip_file.writestr(
            "requirements.txt",
            "streamlit>=1.57\npandas>=2.2\n",
        )
        # Helpful files for users who download and run locally
        zip_file.writestr(
            "README.md",
            """
# Downloaded dashboard

This archive contains a generated Streamlit dashboard. To run locally:

1. Create a Python virtual environment (recommended):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1  # PowerShell
# or .venv\Scripts\activate  # CMD
```

2. Install dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

3. Run the app:

```powershell
python -m streamlit run app.py --server.port 8501
```

If you prefer a one-click script, use `run_local.bat` (Windows) or `run_local.sh` (Linux/macOS).
""",
        )
        zip_file.writestr(
            "run_local.bat",
            """
@echo off
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.port 8501
""",
        )
        zip_file.writestr(
            "run_local.sh",
            """
#!/usr/bin/env bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.port 8501
""",
        )

    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": "attachment; filename=dashboard_project.zip"
        },
    )
