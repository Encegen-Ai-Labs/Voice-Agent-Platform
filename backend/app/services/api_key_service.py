import hashlib
import secrets
from app.core.security import _hash_api_key
from fastapi import HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from app.models import APIKey


def create_api_key(
    db: Session,
    workspace_id: UUID,
    name: str
):

    raw_key = secrets.token_urlsafe(32)

    hashed_key = _hash_api_key(raw_key)

    api_key = APIKey(
        workspace_id=workspace_id,
        name=name,
        key_hash=hashed_key
    )

    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return {
        "id": api_key.id,
        "name": api_key.name,
        "created_at": api_key.created_at,
        "api_key": raw_key
    }


def get_api_keys(
    db: Session,
    workspace_id: UUID
):

    return db.query(APIKey).filter(
        APIKey.workspace_id == workspace_id
    ).all()


def delete_api_key(
    db: Session,
    workspace_id: UUID,
    api_key_id: UUID
):

    api_key = db.query(APIKey).filter(
        APIKey.id == api_key_id,
        APIKey.workspace_id == workspace_id
    ).first()

    if not api_key:
        raise HTTPException(
            status_code=404,
            detail="API key not found"
        )

    db.delete(api_key)
    db.commit()

    return {
        "detail": "API key revoked successfully"
    }