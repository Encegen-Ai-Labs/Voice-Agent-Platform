from sqlalchemy.orm import Session

from app.models.voice import Voice
from app.services.cartesia_service import CartesiaService


async def sync_cartesia_voices(db: Session):
    voices = await CartesiaService.get_voices()

    imported = 0
    updated = 0

    for voice in voices:

        existing = (
            db.query(Voice)
            .filter(
                Voice.provider_voice_id == voice["id"]
            )
            .first()
        )

        if existing:
            existing.name = voice["name"]
            existing.description = voice.get("description")
            existing.gender = voice.get("gender")
            existing.language = voice.get("language")
            existing.is_public = voice.get("is_public", True)
            existing.is_active = True

            updated += 1

        else:
            db.add(
                Voice(
                    provider="cartesia",
                    provider_voice_id=voice["id"],
                    name=voice["name"],
                    description=voice.get("description"),
                    gender=voice.get("gender"),
                    language=voice.get("language"),
                    is_public=voice.get("is_public", True),
                    is_active=True,
                )
            )

            imported += 1

    db.commit()

    return {
        "imported": imported,
        "updated": updated,
        "total": len(voices),
    }