from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas.auth import RegisterRequest, LoginRequest, AuthResponse
from app.services.auth_service import register_user, login_user
from app.core.security import create_access_token, get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = register_user(
        db,
        payload.email,
        payload.password,
        payload.workspace_name
    )

    token = create_access_token({
        "user_id": str(user.id),
        "workspace_id": str(user.workspace_id)
    })

    return {"access_token": token}


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = login_user(db, payload.email, payload.password)

    token = create_access_token({
        "user_id": str(user.id),
        "workspace_id": str(user.workspace_id)
    })

    return {
        "access_token": token
    }


@router.get("/me")
def get_me(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == current_user["user_id"]).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "email": user.email,
        "workspace_name": user.workspace.name if user.workspace else "User"
    }