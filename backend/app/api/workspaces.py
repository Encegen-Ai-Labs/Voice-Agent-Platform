from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.schemas.workspace import (
    WorkspaceCreate,
    WorkspaceResponse,
)
from app.services.workspace_service import (
    create_workspace,
    get_workspace,
)

router = APIRouter(
    prefix="/workspaces",
    tags=["Workspaces"]
)


@router.post(
    "",
    response_model=WorkspaceResponse
)
def create_new_workspace(
    payload: WorkspaceCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    workspace = create_workspace(
        db=db,
        data=payload
    )

    return workspace


@router.get(
    "/me",
    response_model=WorkspaceResponse
)
def get_my_workspace(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    workspace = get_workspace(
        db=db,
        workspace_id=current_user["workspace_id"]
    )

    return workspace