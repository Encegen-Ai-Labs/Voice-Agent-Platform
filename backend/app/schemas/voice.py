from uuid import UUID
from pydantic import BaseModel


class VoiceResponse(BaseModel):
    id: UUID
    provider: str
    provider_voice_id: str
    name: str
    description: str | None = None
    gender: str | None = None
    language: str | None = None
    is_public: bool
    is_active: bool

    class Config:
        from_attributes = True