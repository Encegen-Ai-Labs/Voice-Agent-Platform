from uuid import UUID

from pydantic import BaseModel, field_validator


class OutboundCallRequest(BaseModel):

    agent_id: UUID

    phone_number: str

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(
        cls,
        value: str
    ):

        value = value.strip()

        if not value.startswith("+"):

            raise ValueError(
                "Phone number must be in E.164 format"
            )

        return value