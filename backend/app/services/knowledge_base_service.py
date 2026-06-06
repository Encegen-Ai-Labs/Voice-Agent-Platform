import io

from uuid import UUID

from fastapi import (
    HTTPException,
    UploadFile
)

from sqlalchemy.orm import Session

from PyPDF2 import PdfReader

from app.models import (
    Agent,
    KnowledgeBase
)


MAX_FILE_SIZE = 5 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    ".txt",
    ".pdf"
}


def _validate_file(upload_file: UploadFile):

    filename = (upload_file.filename or "").lower()

    if not filename:
        raise HTTPException(
            status_code=400,
            detail="Filename is required"
        )

    if not any(
        filename.endswith(ext)
        for ext in ALLOWED_EXTENSIONS
    ):
        raise HTTPException(
            status_code=400,
            detail="Only TXT and PDF files are supported"
        )


def _extract_text_from_txt(file_bytes: bytes) -> str:

    try:
        return file_bytes.decode("utf-8").strip()

    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="TXT file must be UTF-8 encoded"
        )


def _extract_text_from_pdf(file_bytes: bytes) -> str:

    try:
        pdf_reader = PdfReader(
            io.BytesIO(file_bytes)
        )

        extracted_pages = []

        for page in pdf_reader.pages:

            page_text = page.extract_text()

            if page_text:
                extracted_pages.append(page_text)

        extracted_text = "\n".join(
            extracted_pages
        ).strip()

        if not extracted_text:
            raise HTTPException(
                status_code=400,
                detail="No readable text found in PDF"
            )

        return extracted_text

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Failed to process PDF file"
        )


def _extract_content(
    upload_file: UploadFile,
    file_bytes: bytes
) -> str:

    filename = upload_file.filename.lower()

    if filename.endswith(".txt"):
        return _extract_text_from_txt(file_bytes)

    if filename.endswith(".pdf"):
        return _extract_text_from_pdf(file_bytes)

    raise HTTPException(
        status_code=400,
        detail="Unsupported file type"
    )


def create_knowledge_base_entry(
    db: Session,
    workspace_id: UUID,
    agent_id: UUID | None,
    upload_file: UploadFile
):

    _validate_file(upload_file)

    file_bytes = upload_file.file.read()

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty"
        )

    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File size exceeds 5MB limit"
        )

    if agent_id:

        agent = db.query(Agent).filter(
            Agent.id == agent_id,
            Agent.workspace_id == workspace_id
        ).first()

        if not agent:
            raise HTTPException(
                status_code=404,
                detail="Agent not found"
            )

    extracted_content = _extract_content(
        upload_file,
        file_bytes
    )

    if not extracted_content.strip():
        raise HTTPException(
            status_code=400,
            detail="Extracted content is empty"
        )

    knowledge_base_entry = KnowledgeBase(
        workspace_id=workspace_id,
        agent_id=agent_id,
        filename=upload_file.filename,
        content=extracted_content
    )
    try:
        db.add(knowledge_base_entry)

        db.commit()

        db.refresh(knowledge_base_entry)

        return knowledge_base_entry
    except HTTPException:
        raise   
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to create knowledge base entry"
        )


def get_knowledge_base_entries(
    db: Session,
    workspace_id: UUID
):

    return db.query(KnowledgeBase).filter(
        KnowledgeBase.workspace_id == workspace_id
    ).order_by(
        KnowledgeBase.created_at.desc()
    ).all()

def get_knowledge_base_entry(
    db: Session,
    workspace_id: UUID,
    knowledge_base_id: UUID
):

    knowledge_base_entry = db.query(
        KnowledgeBase
    ).filter(
        KnowledgeBase.id == knowledge_base_id,
        KnowledgeBase.workspace_id == workspace_id
    ).first()

    if not knowledge_base_entry:
        raise HTTPException(
            status_code=404,
            detail="Knowledge base entry not found"
        )

    return knowledge_base_entry

def delete_knowledge_base_entry(
    db: Session,
    workspace_id: UUID,
    knowledge_base_id: UUID
):

    knowledge_base_entry = db.query(
        KnowledgeBase
    ).filter(
        KnowledgeBase.id == knowledge_base_id,
        KnowledgeBase.workspace_id == workspace_id
    ).first()

    if not knowledge_base_entry:
        raise HTTPException(
            status_code=404,
            detail="Knowledge base entry not found"
        )

    try:
        db.delete(knowledge_base_entry)
        db.commit()

        return {
            "detail": "Knowledge base entry deleted successfully"
        }
    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to delete knowledge base entry"
        )