from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    webhook_url: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str):
        cleaned = value.strip()

        if not cleaned:
            raise ValueError("Workspace name cannot be empty")

        return cleaned


class WorkspaceResponse(BaseModel):
    id: UUID
    name: str
    plan: str
    webhook_url: str | None
    created_at: datetime

    class Config:
        from_attributes = True