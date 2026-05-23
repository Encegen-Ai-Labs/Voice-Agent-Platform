import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.orm import Session

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./voiceforge.db")


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
class Base(DeclarativeBase):
    pass


engine = create_engine(
    DATABASE_URL
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)