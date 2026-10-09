from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from app.core.rate_limit import limiter
from fastapi import Request
from app.database import get_db
from app.core.security import get_current_user
from app.schemas.api_key import (
    APIKeyCreate,
    APIKeyResponse,
    APIKeyCreateResponse
)
from app.services.api_key_service import (
    create_api_key,
    get_api_keys,
    delete_api_key
)


router = APIRouter(
    prefix="/api-keys",
    tags=["API Keys"]
)


@router.post(
    "",
    response_model=APIKeyCreateResponse
)
@limiter.limit("5/minute")
def create_api_key_endpoint(
    request: Request,
    data: APIKeyCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    return create_api_key(
        db,
        current_user["workspace_id"],
        data.name
    )


@router.get(
    "",
    response_model=list[APIKeyResponse]
)
def list_api_keys(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    return get_api_keys(
        db,
        current_user["workspace_id"]
    )


@router.delete("/{api_key_id}")
def revoke_api_key(
    api_key_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    return delete_api_key(
        db,
        current_user["workspace_id"],
        api_key_id
    )