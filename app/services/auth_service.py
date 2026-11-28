import json
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pydantic import BaseModel

# Auth config
USERS_FILE = Path("storage/users/users.json")

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "59438908cf083f26877e255a08ee838128afdcd2f419364c7eab7a7a32cfd3f2",
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # One-week token lifetime

# Auth scheme
# tokenUrl points to the token endpoint. Auth routes are mounted with the /auth prefix,
# so we specify the full /auth/token path for Swagger Authorize to work properly.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

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
    name: str | None = None
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


# Create an access token for subsequent authentication
def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Retrieve user after verifying the provided email and password
def authenticate_user(db, email: str, password: str):
    user = get_user_by_email(db, email)
    if not user:
        # Fake verify to protect from timing attacks
        verify_password(password, DUMMY_HASH)
        return False
    if not verify_password(password, user.passwordHash):
        return False
    return user

# Retrieve user by token
async def get_current_user_by_token(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # Extract the current user's id embedded in the token
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id)
    except InvalidTokenError as error:
        raise credentials_exception from error

    if token_data.user_id is None:
        raise credentials_exception

    users = _load_users()
    user = get_user_by_id(db=users, user_id=token_data.user_id)
    if user is None:
        raise credentials_exception
    return User(
        id=user.id,
        email=user.email,
        name=user.name,
        createdAt=user.createdAt,
        disabled=user.disabled,
    )

# Retrieve only a currently active user
async def get_current_active_user(
        current_user: Annotated[User, Depends(get_current_user_by_token)],
):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Log in a user to issue a token for subsequent authentication
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


# Register a new user
def register_user(email: str, password: str, name: str | None = None) -> User:
    email = email.strip().lower()
    name = name.strip() if name else None

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


    user_id = str(uuid.uuid4())
    user_dict = {
        "id": user_id,
        "email": email,
        "name": name,
        "passwordHash": get_password_hash(password),
        "createdAt": datetime.now(UTC).isoformat(),
        "disabled": False,
    }

    # Add the newly created user to the shared users file
    users[user_id] = user_dict
    _save_users(users)

    return User(
        id=user_dict["id"],
        email=user_dict["email"],
        name=user_dict["name"],
        createdAt=user_dict["createdAt"],
        disabled=user_dict["disabled"],
    )


def change_user_password(
    user_id: str,
    current_password: str,
    new_password: str,
) -> None:
    if len(new_password) < 6:
        raise ValueError("Password must contain at least 6 characters")

    users = _load_users()
    user = users.get(user_id)
    if user is None or not verify_password(current_password, user["passwordHash"]):
        raise ValueError("Current password is incorrect")

    user["passwordHash"] = get_password_hash(new_password)
    _save_users(users)
