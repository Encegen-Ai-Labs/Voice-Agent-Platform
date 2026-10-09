import hashlib

from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext

from fastapi import (
    Depends,
    HTTPException,
    Header
)

from fastapi.security import (
    HTTPBearer,
    HTTPAuthorizationCredentials
)

from sqlalchemy.orm import Session
from uuid import UUID

from app.core.config import settings
from app.database import get_db
from app.models import APIKey


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def hash_password(password: str) -> str:

    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:

    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict) -> str:

    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_EXPIRE_MINUTES
    )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


security = HTTPBearer(auto_error=False)


def _hash_api_key(raw_key: str) -> str:

    return hashlib.sha256(
        raw_key.encode()
    ).hexdigest()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: Session = Depends(get_db)
):

    # API Key auth
    if x_api_key:

        hashed_key = _hash_api_key(x_api_key)

        api_key = db.query(APIKey).filter(
            APIKey.key_hash == hashed_key
        ).first()

        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )

        return {
            "user_id": None,
            "workspace_id": api_key.workspace_id
        }

    # JWT auth
    if credentials:

        try:
            token = credentials.credentials

            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )

            user_id = payload.get("user_id")
            workspace_id = payload.get("workspace_id")

            if not user_id or not workspace_id:
                raise HTTPException(
                    status_code=401,
                    detail="Invalid token payload"
                )

            return {
                "user_id": UUID(user_id),
                "workspace_id": UUID(workspace_id)
            }

        except JWTError:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )

    raise HTTPException(
        status_code=401,
        detail="Authentication required"
    )