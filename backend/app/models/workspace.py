import uuid
from datetime import datetime, timezone

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Workspace(Base):
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )

    name: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    plan: Mapped[str] = mapped_column(
        String,
        default="free"
    )

    webhook_url: Mapped[str | None] = mapped_column(
        String,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    # relationships
    users: Mapped[list["User"]] = relationship(
        back_populates="workspace"
    )

    agents: Mapped[list["Agent"]] = relationship(
        back_populates="workspace"
    )

    phone_numbers: Mapped[list["PhoneNumber"]] = relationship(
        back_populates="workspace"
    )

    calls: Mapped[list["Call"]] = relationship(
        back_populates="workspace"
    )

    api_keys: Mapped[list["APIKey"]] = relationship(
      back_populates="workspace"
    )
      
    knowledge_base_entries: Mapped[list["KnowledgeBase"]] = relationship(
      back_populates="workspace"
    )
