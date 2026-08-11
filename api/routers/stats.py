from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import get_current_user, get_db
from api.schemas.stats import RunStatOut
from api.services.stats_service import StatsService

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=list[RunStatOut])
def get_stats(db: Session = Depends(get_db), user=Depends(get_current_user)):
    service = StatsService(db)
    return service.get_run_stats()
