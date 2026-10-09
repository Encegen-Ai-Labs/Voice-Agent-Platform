from fastapi import (
    APIRouter,
    Depends,
    Query
)

from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db

from app.schemas.analytics import (
    CallAnalyticsResponse
)

from app.services.analytics_service import (
    get_call_analytics
)


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"]
)


@router.get(
    "/calls",
    response_model=CallAnalyticsResponse
)
def get_calls_analytics(
    days: int = Query(default=7, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):

    return get_call_analytics(
        db=db,
        workspace_id=current_user["workspace_id"],
        days=days
    )