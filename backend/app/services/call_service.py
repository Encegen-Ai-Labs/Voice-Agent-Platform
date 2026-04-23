from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from app.models import Call, Agent


def create_call(db: Session, workspace_id: UUID, data):
    agent = db.query(Agent).filter(
        Agent.id == data.agent_id,
        Agent.workspace_id == workspace_id
    ).first()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found in this workspace")

    call = Call(
        workspace_id=workspace_id,
        agent_id=data.agent_id,
        phone_number=data.phone_number,
        direction=data.direction,
        status="initiated"
    )

    db.add(call)
    db.commit()
    db.refresh(call)
    return call


def get_calls(db: Session, workspace_id: UUID):
    return db.query(Call).filter(
        Call.workspace_id == workspace_id
    ).all()


def get_call(db: Session, workspace_id: UUID, call_id: UUID):
    call = db.query(Call).filter(
        Call.id == call_id,
        Call.workspace_id == workspace_id
    ).first()

    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    return call


def update_call(db: Session, workspace_id: UUID, call_id: UUID, data):
    call = get_call(db, workspace_id, call_id)

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(call, field, value)

    db.commit()
    db.refresh(call)
    return call
