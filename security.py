import logging
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from pydantic_settings import BaseSettings, SettingsConfigDict


logger = logging.getLogger("ecosense.security")


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    secret_key: str = ""
    access_token_minutes: int = 60


auth_settings = AuthSettings()

if not auth_settings.secret_key:
    auth_settings.secret_key = secrets.token_hex(32)
    logger.warning("SECRET_KEY is not set; using a temporary key.")

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")

    if len(raw) > 72:
        raise ValueError("Password must be at most 72 bytes")

    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, company_id: int, role: str) -> str:
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=auth_settings.access_token_minutes
    )

    payload = {
        "sub": str(user_id),
        "company_id": company_id,
        "role": role,
        "exp": expires,
    }

    return jwt.encode(
        payload,
        auth_settings.secret_key,
        algorithm=ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        auth_settings.secret_key,
        algorithms=[ALGORITHM],
    )