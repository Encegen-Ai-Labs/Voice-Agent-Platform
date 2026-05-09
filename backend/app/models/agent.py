import uuid
from datetime import datetime, timezone
from sqlalchemy import String, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.id")
    )

    name: Mapped[str] = mapped_column(String, nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(String)
    voice: Mapped[str | None] = mapped_column(String)
    llm_model: Mapped[str | None] = mapped_column(String)
    language: Mapped[str | None] = mapped_column(String)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # relationships
    workspace: Mapped["Workspace"] = relationship(back_populates="agents")
    phone_numbers: Mapped[list["PhoneNumber"]] = relationship(back_populates="agent")
    calls: Mapped[list["Call"]] = relationship(back_populates="agent")
    knowledge_base_entries: Mapped[list["KnowledgeBase"]] = relationship(back_populates="agent")