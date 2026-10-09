from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.workspace import Workspace


def create_workspace(
    db: Session,
    data
):
    workspace = Workspace(
        name=data.name.strip(),
        webhook_url=data.webhook_url
    )

    try:
        db.add(workspace)
        db.commit()
        db.refresh(workspace)

        return workspace

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Failed to create workspace"
        )


def get_workspace(
    db: Session,
    workspace_id: UUID
):
    workspace = db.query(Workspace).filter(
        Workspace.id == workspace_id
    ).first()

    if not workspace:
        raise HTTPException(
            status_code=404,
            detail="Workspace not found"
        )

    return workspace