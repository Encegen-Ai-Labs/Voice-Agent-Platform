from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models import User, Workspace
from app.core.security import hash_password, verify_password, create_access_token


def register_user(db: Session, email: str, password: str, workspace_name: str):
    # Check if user exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists."
        )

    try:
        # Create workspace
        workspace = Workspace(name=workspace_name)
        db.add(workspace)
        db.flush()

        # Create user
        user = User(
            email=email.strip().lower(),
            password_hash=hash_password(password),
            workspace_id=workspace.id,
            role="owner"
        )
        db.add(user)
        db.commit()

        return user

    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Registration failed")


def login_user(db: Session, email: str, password: str):
    user = db.query(User).filter(User.email == email).first()

    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return user