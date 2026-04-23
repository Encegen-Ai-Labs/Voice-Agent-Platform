from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from uuid import UUID
from app.database import get_db
from app.core.security import get_current_user
from app.models import Agent
from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse
from app.services.agent_service import (
    create_agent,
    get_agents,
    get_agent,
    update_agent,
    delete_agent
)

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post("", response_model=AgentResponse)
def create_agent_endpoint(
    data: AgentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return create_agent(db, current_user["workspace_id"], data)


@router.get("", response_model=list[AgentResponse])
def list_agents(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return get_agents(db, current_user["workspace_id"])


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent_endpoint(
    agent_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return get_agent(db, current_user["workspace_id"], agent_id)


@router.put("/{agent_id}", response_model=AgentResponse)
def update_agent_endpoint(
    agent_id: UUID,
    data: AgentUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return update_agent(db, current_user["workspace_id"], agent_id, data)


@router.delete("/{agent_id}")
def delete_agent_endpoint(
    agent_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    return delete_agent(db, current_user["workspace_id"], agent_id)