from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.core.security import get_current_user
from app.schemas.call import CallCreate, CallUpdate, CallResponse
from app.services.call_service import (
    create_call,
    get_calls,
    get_call,
    update_call,
    delete_call
)

router = APIRouter(prefix="/calls", tags=["Calls"])


@router.post("", response_model=CallResponse)
def create_call_endpoint(
    data: CallCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return create_call(db, current_user["workspace_id"], data)


@router.get("", response_model=list[CallResponse])
def list_calls(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return get_calls(db, current_user["workspace_id"])


@router.get("/{call_id}", response_model=CallResponse)
def get_call_endpoint(
    call_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return get_call(db, current_user["workspace_id"], call_id)


@router.put("/{call_id}", response_model=CallResponse)
def update_call_endpoint(
    call_id: UUID,
    data: CallUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return update_call(db, current_user["workspace_id"], call_id, data)

@router.delete("/{call_id}")
def delete_call_endpoint(
    call_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return delete_call(db, current_user["workspace_id"], call_id)