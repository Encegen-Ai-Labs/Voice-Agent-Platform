from sqlalchemy.orm import Session

from app.models.voice import Voice


def get_all_voices(db: Session):
    return (
        db.query(Voice)
        .filter(
            Voice.is_active == True,
            Voice.is_public == True,
            Voice.language == "en",
        )
        .order_by(Voice.name)
        .all()
    )