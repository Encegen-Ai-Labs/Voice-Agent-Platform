from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Agent
from app.models.call import Call
from app.models.phone_number import PhoneNumber


def create_agent(db: Session, workspace_id: UUID, data):
    agent = Agent(
        workspace_id=workspace_id,
        name=data.name.strip(),
        system_prompt=data.system_prompt,
        voice=data.voice,
        llm_model=data.llm_model,
        language=data.language,
        is_active=True
    )

    try:

            db.add(agent)

            db.commit()

            db.refresh(agent)

            return agent

    except HTTPException:
            raise

    except Exception:

            db.rollback()

            raise HTTPException(
                status_code=500,
                detail="Failed to create agent"
            )


def get_agents(db: Session, workspace_id: UUID):
    return db.query(Agent).filter(
        Agent.workspace_id == workspace_id
    ).all()


def get_agent(db: Session, workspace_id: UUID, agent_id: UUID):
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.workspace_id == workspace_id
    ).first()

    if not agent:
        raise HTTPException(
            status_code=404,
            detail="Agent not found"
        )

    return agent


def update_agent(
    db: Session,
    workspace_id: UUID,
    agent_id: UUID,
    data
):
    agent = get_agent(
        db,
        workspace_id,
        agent_id
    )

    update_data = data.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(agent, field, value)

    try:
        db.commit()
        db.refresh(agent)

        return agent
    except HTTPException:
            raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to update agent"
        )


def delete_agent(
    db: Session,
    workspace_id: UUID,
    agent_id: UUID
):
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.workspace_id == workspace_id
    ).first()

    if not agent:
        raise HTTPException(
            status_code=404,
            detail="Agent not found"
        )

    # Preserve phone numbers
    linked_numbers = db.query(PhoneNumber).filter(
        PhoneNumber.agent_id == agent_id
    ).all()

    for number in linked_numbers:
        number.agent_id = None

    # Delete related calls
    try:
        db.query(Call).filter(
           Call.agent_id == agent_id,
           Call.workspace_id == workspace_id
           ).delete()

        db.delete(agent)
        db.commit()

        return {
            "message": "Agent deleted successfully"
        }
    except HTTPException:
            raise

    except Exception:

            db.rollback()

            raise HTTPException(
                status_code=500,
                detail="Failed to delete agent"
            )