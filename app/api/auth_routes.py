from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, Depends
from fastapi.responses import PlainTextResponse, StreamingResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

# Services
from app.services import auth_service

router = APIRouter(prefix="/auth")


class PasswordChangePayload(BaseModel):
    currentPassword: str
    newPassword: str


# УПРАВЛЕНИЕ LOGIN
@router.post("/register")
def register(payload: dict):
    try:
        return auth_service.register_user(
            email=payload.get("email", ""),
            password=payload.get("password", ""),
            name=payload.get("name"),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

@router.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    # В этом случае form_data.username хранит email пользователя
    return auth_service.login_user(email=form_data.username, password=form_data.password)

@router.get("/me")
def auth_me(current_user: Annotated[auth_service.User, Depends(auth_service.get_current_active_user)]):
    return current_user


@router.put("/password")
def change_password(
    payload: PasswordChangePayload,
    current_user: Annotated[
        auth_service.User,
        Depends(auth_service.get_current_active_user),
    ],
):
    try:
        auth_service.change_user_password(
            user_id=current_user.id,
            current_password=payload.currentPassword,
            new_password=payload.newPassword,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    return {"message": "Password changed successfully"}