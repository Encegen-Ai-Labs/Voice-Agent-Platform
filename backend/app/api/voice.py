from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_current_user
from app.schemas.voice import VoiceResponse
from app.services.voice_service import get_all_voices
from app.services.voice_sync_service import sync_cartesia_voices

router = APIRouter(
    prefix="/voices",
    tags=["Voices"],
)


@router.get(
    "",
    response_model=list[VoiceResponse],
)
def list_voices(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return get_all_voices(db)


@router.post("/sync")
async def sync_voices(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return await sync_cartesia_voices(db)