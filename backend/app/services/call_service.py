import logging
from subprocess import call
import threading

import httpx

from fastapi import HTTPException
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime

from app.models import UsageRecord
from app.models import Call, Agent


logger = logging.getLogger(__name__)


def _send_call_webhook(call: Call):

    webhook_url = call.workspace.webhook_url

    if not webhook_url:
        return

    payload = {
        "call_id": str(call.id),
        "agent_id": str(call.agent_id),
        "status": call.status,
        "transcript": call.transcript,
        "sentiment": call.sentiment,
        "duration": call.duration
    }

    try:
        response = httpx.post(
            webhook_url,
            json=payload,
            timeout=10.0
        )

        response.raise_for_status()

    except Exception:
        logger.exception(
            "Failed to send webhook for call %s",
            call.id
        )


def _trigger_webhook_background(call: Call):

    thread = threading.Thread(
        target=_send_call_webhook,
        args=(call,),
        daemon=True
    )

    thread.start()


def create_call(db: Session, workspace_id: UUID, data):

    agent = db.query(Agent).filter(
        Agent.id == data.agent_id,
        Agent.workspace_id == workspace_id
    ).first()

    if not agent:
        raise HTTPException(
            status_code=404,
            detail="Agent not found in this workspace"
        )

    call = Call(
        workspace_id=workspace_id,
        agent_id=data.agent_id,
        phone_number=data.phone_number,
        direction=data.direction,
        status="initiated"
    )
    try:
        db.add(call)
        db.commit()
        db.refresh(call)

        return call
    except HTTPException:
        raise
    except Exception:  
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to create call"
        )


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
        raise HTTPException(
            status_code=404,
            detail="Call not found"
        )

    return call

def _update_usage_tracking(
    db: Session,
    call: Call
):

    if not call.duration:
        return

    now = datetime.utcnow()

    month = now.month
    year = now.year

    duration_minutes = round(call.duration / 60, 2)

    usage_record = db.query(
        UsageRecord
    ).filter(
        UsageRecord.workspace_id == call.workspace_id,
        UsageRecord.month == month,
        UsageRecord.year == year
    ).first()

    if usage_record:

        usage_record.total_minutes += duration_minutes

    else:

        usage_record = UsageRecord(
            workspace_id=call.workspace_id,
            month=month,
            year=year,
            total_minutes=duration_minutes
        )

        db.add(usage_record)

    

def update_call(db: Session, workspace_id: UUID, call_id: UUID, data):

    call = get_call(db, workspace_id, call_id)

    previous_status = call.status

    update_data = data.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(call, field, value)

    try:
        db.commit()
        db.refresh(call)

        terminal_statuses = {"completed", "failed"}

        should_trigger_webhook = (
            previous_status != call.status
            and call.status in terminal_statuses
        )

        if should_trigger_webhook:
            if call.status == "completed":

                _update_usage_tracking(
                    db,
                    call
                )
            _trigger_webhook_background(call)
        db.commit()
        db.refresh(call)

        return call
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to update call"
        )


def delete_call(db: Session, workspace_id: UUID, call_id: UUID):

    call = db.query(Call).filter(
        Call.id == call_id,
        Call.workspace_id == workspace_id
    ).first()

    if not call:
        raise HTTPException(
            status_code=404,
            detail="Call not found"
        )

    try:
        db.delete(call)
        db.commit()

        return {"detail": "Call deleted successfully"}
    except HTTPException:
        raise   
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to delete call"
        )