from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

# Services
from app.services import auth_service

router = APIRouter(prefix="/auth")


class RegisterPayload(BaseModel):
    email: str
    password: str
    name: str | None = None


class PasswordChangePayload(BaseModel):
    currentPassword: str
    newPassword: str


# LOGIN MANAGEMENT
@router.post("/register")
def register(payload: RegisterPayload):
    try:
        return auth_service.register_user(
            email=payload.email,
            password=payload.password,
            name=payload.name,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

@router.post("/token")
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    # In this case form_data.username stores the user's email
    return auth_service.login_user(email=form_data.username, password=form_data.password)

@router.get("/me", response_model=auth_service.User)
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
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"message": "Password changed successfully"}