from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class KnowledgeBaseResponse(BaseModel):

    id: UUID
    workspace_id: UUID
    agent_id: UUID | None
    filename: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeBaseListResponse(BaseModel):

    id: UUID
    workspace_id: UUID
    agent_id: UUID | None
    filename: str
    created_at: datetime

    class Config:
        from_attributes = True