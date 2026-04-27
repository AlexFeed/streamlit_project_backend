from fastapi import Header, HTTPException

from app.services.auth_service import get_user_from_token


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header is required",
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header",
        )

    token = authorization.replace("Bearer ", "").strip()

    try:
        user = get_user_from_token(token)
    except ValueError as error:
        raise HTTPException(status_code=401, detail=str(error))

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user