import uuid
from datetime import datetime, timezone

from sqlalchemy import String, ForeignKey, DateTime, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Call(Base):
    __tablename__ = "calls"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id")
    )

    agent_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("agents.id")
    )

    phone_number: Mapped[str | None] = mapped_column(String)

    status: Mapped[str | None] = mapped_column(String)

    transcript: Mapped[str | None] = mapped_column(String)

    recording_url: Mapped[str | None] = mapped_column(String)

    sentiment: Mapped[str | None] = mapped_column(String)

    direction: Mapped[str | None] = mapped_column(String)

    twilio_call_sid: Mapped[str | None] = mapped_column(String, unique=True)

    start_time: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    end_time: Mapped[datetime | None] = mapped_column(DateTime)

    duration: Mapped[int | None] = mapped_column(Integer)

    # relationships
    agent: Mapped["Agent"] = relationship(
        back_populates="calls"
    )

    workspace: Mapped["Workspace"] = relationship(
        back_populates="calls"
    )