from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.phone_number import PhoneNumber


def create_phone_number(
    db: Session,
    workspace_id: UUID,
    data
):
    existing_number = db.query(PhoneNumber).filter(
        PhoneNumber.number == data.number
    ).first()

    if existing_number:
        raise HTTPException(
            status_code=400,
            detail="Phone number already exists"
        )

    if data.agent_id:
        agent = db.query(Agent).filter(
            Agent.id == data.agent_id,
            Agent.workspace_id == workspace_id
        ).first()

        if not agent:
            raise HTTPException(
                status_code=404,
                detail="Agent not found in this workspace"
            )

    phone_number = PhoneNumber(
        workspace_id=workspace_id,
        agent_id=data.agent_id,
        type=data.type,
        number=data.number.strip()
    )

    try:
        db.add(phone_number)
        db.commit()
        db.refresh(phone_number)

        return phone_number

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to create phone number"
        )


def get_phone_numbers(
    db: Session,
    workspace_id: UUID
):
    return db.query(PhoneNumber).filter(
        PhoneNumber.workspace_id == workspace_id
    ).all()


def delete_phone_number(
    db: Session,
    workspace_id: UUID,
    phone_number_id: UUID
):
    phone_number = db.query(PhoneNumber).filter(
        PhoneNumber.id == phone_number_id,
        PhoneNumber.workspace_id == workspace_id
    ).first()

    if not phone_number:
        raise HTTPException(
            status_code=404,
            detail="Phone number not found"
        )

    db.delete(phone_number)
    db.commit()

    return {
        "detail": "Phone number deleted successfully"
    }