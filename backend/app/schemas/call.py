from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class CallCreate(BaseModel):
    agent_id: UUID
    phone_number: str | None = None
    direction: str | None = None


class CallUpdate(BaseModel):
    status: str | None = None
    transcript: str | None = None
    sentiment: str | None = None
    duration: int | None = None
    recording_url: str | None = None
    end_time: datetime | None = None


class CallResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    agent_id: UUID
    phone_number: str | None
    status: str | None
    transcript: str | None
    recording_url: str | None
    sentiment: str | None
    direction: str | None
    start_time: datetime
    end_time: datetime | None
    duration: int | None

    class Config:
        from_attributes = True