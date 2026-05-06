import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from pydantic import BaseModel
from typing import Annotated

from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi import FastAPI, Depends, HTTPException, status

from pwdlib import PasswordHash
import jwt
from jwt.exceptions import InvalidTokenError

# Auth config
USERS_FILE = Path("storage/users/users.json")

SECRET_KEY = "59438908cf083f26877e255a08ee838128afdcd2f419364c7eab7a7a32cfd3f2"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # Неделя жизни токена

# Auth scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Password hashing configs
password_hash = PasswordHash.recommended()
DUMMY_HASH = password_hash.hash("dummypassword")

# Token models
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: str | None = None


# User models
class User(BaseModel):
    id: str
    email: str
    createdAt: datetime | None = None
    disabled: bool | None = None

class UserInDB(User):
    passwordHash: str


# Helper functions
def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)

def get_password_hash(password):
    return password_hash.hash(password)

def get_user_by_email(db: dict, email: str):
    normalized_email = email.strip().lower()

    for user in db.values():
        if user["email"] == normalized_email:
            return UserInDB(**user)

    return None

def get_user_by_id(db: dict, user_id: str):
    user = db.get(user_id)
    return UserInDB(**user) if user else None


# Functions for work with JSON users data
def _ensure_users_file() -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not USERS_FILE.exists():
        with USERS_FILE.open("w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)


def _load_users() -> dict[str, dict]:
    _ensure_users_file()

    with USERS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(users: dict[str, dict]) -> None:
    _ensure_users_file()

    with USERS_FILE.open("w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


# Создание токена для дальнейшей аутентефикации по нему
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Получения пользователя после проверки правильности введённого email и пароля
def authenticate_user(db, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user:
        # Fake verify to protect from timing attacks
        verify_password(password, DUMMY_HASH)
        return False
    if not verify_password(password, user.passwordHash):
        return False
    return user

# Получение пользователя по токену
async def get_current_user_by_token(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Извлекается id текущего пользователя, зашитый в токен
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id = user_id)
    except InvalidTokenError:
        raise credentials_exception

    users = _load_users()
    user = get_user_by_id(db=users, user_id=token_data.user_id)
    if user is None:
        raise credentials_exception
    return user

# Получение только активного на данный момент пользователя
async def get_current_active_user(
        current_user: Annotated[User, Depends(get_current_user_by_token)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Вход пользователя для формирования токена, с которым он дальше будет аутентефицироваться
def login_user(email: str, password: str) -> Token:
    users = _load_users()
    user = authenticate_user(db=users, email=email, password=password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
    )


# Регистрация нового пользователя
def register_user(email: str, password: str) -> dict:
    email = email.strip().lower()

    if not email:
        raise ValueError("Email is required")

    if not password:
        raise ValueError("Password is required")

    if len(password) < 6:
        raise ValueError("Password must contain at least 6 characters")

    users = _load_users()
    is_existing_user = get_user_by_email(db=users, email=email)

    if is_existing_user:
        raise ValueError("User already exists")


    user_id =str(uuid.uuid4())
    user_dict = {
        "id": user_id,
        "email": email,
        "passwordHash": get_password_hash(password),
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "disabled": False,
    }

    # Добавление нового сформированного пользователя в общий файл со всеми пользователями
    users[user_id] = user_dict
    _save_users(users)

    return User(
        id=user_dict["id"],
        email=user_dict["email"],
        createdAt=user_dict["createdAt"],
        disabled=user_dict["disabled"],
    )
