from sqlalchemy.orm import Session
from fastapi import HTTPException
from uuid import UUID
from app.models import Agent


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
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def get_agents(db: Session, workspace_id: UUID):
    return db.query(Agent).filter(Agent.workspace_id == workspace_id).all()


def get_agent(db: Session, workspace_id: UUID, agent_id: UUID):
    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.workspace_id == workspace_id
    ).first()

    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    return agent


def update_agent(db: Session, workspace_id: UUID, agent_id: UUID, data):
    agent = get_agent(db, workspace_id, agent_id)

    for field, value in data.dict(exclude_unset=True).items():
        if value is None or value == "string":
            continue
        setattr(agent, field, value)

    db.commit()
    db.refresh(agent)
    return agent


def delete_agent(db: Session, workspace_id: UUID, agent_id: UUID):
    agent = get_agent(db, workspace_id, agent_id)

    db.delete(agent)
    db.commit()
    return {"detail": "Agent deleted successfully"}