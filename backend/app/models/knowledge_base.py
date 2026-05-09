import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String,
    ForeignKey,
    DateTime,
    Text
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)

from app.database import Base


class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id"),
        nullable=False
    )

    agent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agents.id"),
        nullable=True
    )

    filename: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    workspace: Mapped["Workspace"] = relationship(
        back_populates="knowledge_base_entries"
    )

    agent: Mapped["Agent"] = relationship(
        back_populates="knowledge_base_entries"
    )