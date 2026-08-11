from typing import List

from sqlalchemy.orm import Session

from db.models import RunLog


class StatsService:
    def __init__(self, session: Session):
        self._session = session

    def get_run_stats(self) -> List[RunLog]:
        return self._session.query(RunLog).order_by(RunLog.run_date.asc()).all()
