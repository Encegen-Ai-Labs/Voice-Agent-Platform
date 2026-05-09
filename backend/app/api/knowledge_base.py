from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    UploadFile
)

from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db

from app.schemas.knowledge_base import (
    KnowledgeBaseResponse
)

from app.services.knowledge_base_service import (
    create_knowledge_base_entry,
    get_knowledge_base_entries,
    delete_knowledge_base_entry
)


router = APIRouter(
    prefix="/knowledge-base",
    tags=["Knowledge Base"]
)


@router.post(
    "",
    response_model=KnowledgeBaseResponse
)
def upload_knowledge_base(
    file: UploadFile = File(...),
    agent_id: UUID | None = Form(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    return create_knowledge_base_entry(
        db=db,
        workspace_id=current_user["workspace_id"],
        agent_id=agent_id,
        upload_file=file
    )


@router.get(
    "",
    response_model=list[KnowledgeBaseResponse]
)
def list_knowledge_base_entries(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    return get_knowledge_base_entries(
        db,
        current_user["workspace_id"]
    )


@router.delete("/{knowledge_base_id}")
def delete_knowledge_base(
    knowledge_base_id: UUID,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    return delete_knowledge_base_entry(
        db,
        current_user["workspace_id"],
        knowledge_base_id
    )