from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db

from app.schemas.phone_number import (
    PhoneNumberCreate,
    PhoneNumberResponse,
)

from app.services.phone_number_service import (
    create_phone_number,
    get_phone_numbers,
    delete_phone_number,
)

router = APIRouter(
    prefix="/phone-numbers",
    tags=["Phone Numbers"]
)


@router.post(
    "",
    response_model=PhoneNumberResponse
)
def create_new_phone_number(
    payload: PhoneNumberCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    phone_number = create_phone_number(
        db=db,
        workspace_id=current_user["workspace_id"],
        data=payload
    )

    return phone_number


@router.get(
    "",
    response_model=list[PhoneNumberResponse]
)
def get_workspace_phone_numbers(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    phone_numbers = get_phone_numbers(
        db=db,
        workspace_id=current_user["workspace_id"]
    )

    return phone_numbers


@router.delete("/{phone_number_id}")
def delete_workspace_phone_number(
    phone_number_id: UUID,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    result = delete_phone_number(
        db=db,
        workspace_id=current_user["workspace_id"],
        phone_number_id=phone_number_id
    )

    return result