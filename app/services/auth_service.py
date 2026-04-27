import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from jose import JWTError, jwt
from passlib.context import CryptContext

USERS_FILE = Path("storage/users/users.json")

SECRET_KEY = "dev-secret-key-change-later"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _ensure_users_file() -> None:
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not USERS_FILE.exists():
        with USERS_FILE.open("w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)


def _load_users() -> list[dict]:
    _ensure_users_file()

    with USERS_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_users(users: list[dict]) -> None:
    _ensure_users_file()

    with USERS_FILE.open("w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(user_id: str) -> str:
    expires_at = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    payload = {
        "sub": user_id,
        "exp": expires_at,
    }

    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_user_by_email(email: str) -> dict | None:
    users = _load_users()
    normalized_email = email.strip().lower()

    return next(
        (user for user in users if user["email"] == normalized_email),
        None,
    )


def get_user_by_id(user_id: str) -> dict | None:
    users = _load_users()

    return next(
        (user for user in users if user["id"] == user_id),
        None,
    )


def register_user(email: str, password: str) -> dict:
    email = email.strip().lower()

    if not email:
        raise ValueError("Email is required")

    if not password:
        raise ValueError("Password is required")

    if len(password) < 6:
        raise ValueError("Password must contain at least 6 characters")

    users = _load_users()

    existing_user = next(
        (user for user in users if user["email"] == email),
        None,
    )

    if existing_user:
        raise ValueError("User already exists")

    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password is too long (max 72 bytes)")

    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "passwordHash": hash_password(password),
        "createdAt": _now(),
    }

    users.append(user)
    _save_users(users)

    access_token = create_access_token(user["id"])

    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
        },
        "accessToken": access_token,
    }


def login_user(email: str, password: str) -> dict:
    user = get_user_by_email(email)

    if not user:
        raise ValueError("Invalid email or password")

    if not verify_password(password, user["passwordHash"]):
        raise ValueError("Invalid email or password")

    access_token = create_access_token(user["id"])

    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
        },
        "accessToken": access_token,
    }


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise ValueError("Invalid or expired token")


def get_user_from_token(token: str) -> dict | None:
    payload = decode_token(token)

    user_id = payload.get("sub")

    if not user_id:
        return None

    user = get_user_by_id(user_id)

    if not user:
        return None

    return {
        "id": user["id"],
        "email": user["email"],
    }