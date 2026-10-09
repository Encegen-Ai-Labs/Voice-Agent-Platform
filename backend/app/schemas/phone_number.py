import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


E164_REGEX = re.compile(r"^\+[1-9]\d{7,14}$")


class PhoneNumberCreate(BaseModel):
    number: str = Field(..., min_length=8, max_length=20)
    type: str | None = "both"
    agent_id: UUID | None = None

    @field_validator("number")
    @classmethod
    def validate_number(cls, value: str):
        cleaned = value.strip()

        if not E164_REGEX.match(cleaned):
            raise ValueError(
                "Phone number must be in E.164 format"
            )

        return cleaned


class PhoneNumberResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    agent_id: UUID | None
    type: str
    number: str
    created_at: datetime

    class Config:
        from_attributes = True