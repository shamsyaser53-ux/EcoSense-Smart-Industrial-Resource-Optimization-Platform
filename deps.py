from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
from auth_models import User
from security import decode_access_token


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_optional_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_optional_user(
    token: str | None = Depends(oauth2_optional_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if not token:
        return None
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
        company_id = int(payload["company_id"])
    except Exception:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active or user.company_id != company_id:
        return None

    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired login token",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
        company_id = int(payload["company_id"])
    except Exception:
        raise unauthorized

    user = db.query(User).filter(User.id == user_id).first()

    if user is None or not user.is_active or user.company_id != company_id:
        raise unauthorized

    return user


def require_roles(*allowed_roles: str):
    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return role_checker