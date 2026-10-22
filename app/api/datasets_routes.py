from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from app.services import auth_service, dataset_service

router = APIRouter(prefix="/datasets")

# CRUD ЗАПРОСЫ ДЛЯ ВЗАИМОДЕЙСТВИЯ С ДАТАСЕТАМИ
@router.post("/upload")
async def upload_dataset(
        current_user: Annotated[auth_service.User, Depends(auth_service.get_current_active_user)],
        dataset: UploadFile = File(...),
        name: Annotated[str | None, Form()] = None,
        delimiter: Annotated[str | None, Form()] = None,
        sheet_name: Annotated[str | None, Form(alias="sheetName")] = None,
):
    try:
        return dataset_service.save_dataset(
            user_id=current_user.id,
            file=dataset,
            custom_name=name,
            delimiter=delimiter,
            sheet_name=sheet_name,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения датасета: {error}")


@router.get("/{dataset_id}")
async def get_dataset(
        dataset_id: str,
        current_user: Annotated[
            auth_service.User,
            Depends(auth_service.get_current_active_user),
        ],
):
    meta = dataset_service.get_dataset_meta(current_user.id, dataset_id)

    if not meta:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return meta


@router.get("/{dataset_id}/preview")
async def get_dataset_preview(
        dataset_id: str,
        current_user: Annotated[
            auth_service.User,
            Depends(auth_service.get_current_active_user),
        ],
        limit: int = Query(default=500, ge=1, le=1000),
):
    try:
        preview = dataset_service.get_dataset_preview(
            current_user.id,
            dataset_id,
            limit,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if not preview:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return preview


@router.delete("/{dataset_id}")
async def delete_dataset(
        dataset_id: str,
        current_user: Annotated[
            auth_service.User,
            Depends(auth_service.get_current_active_user),
        ],
):
    deleted = dataset_service.delete_dataset(current_user.id, dataset_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Dataset not found")

    return {"deleted": True}

# Загрузка всех листов с excel файла
@router.post("/inspect-sheets")
async def inspect_sheets(
        current_user: Annotated[
            auth_service.User,
            Depends(auth_service.get_current_active_user),
        ],
        file: UploadFile = File(...),
):
    try:
        sheets = dataset_service.inspect_excel_sheets(file)
        return {"sheets": sheets}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    except Exception as error:
        raise HTTPException(status_code=500, detail=f"Ошибка чтения книги Excel: {error}")