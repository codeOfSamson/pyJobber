from typing import List, Optional

from sqlalchemy.orm import Session

from db.models import JobApplication


class ApplicationService:
    def __init__(self, session: Session):
        self._session = session

    def list_filtered(
        self,
        site: Optional[str] = None,
        status: Optional[str] = None,
        reviewed: Optional[bool] = None,
        needs_review: Optional[bool] = None,
    ) -> List[JobApplication]:
        query = self._session.query(JobApplication)
        if site is not None:
            query = query.filter(JobApplication.site == site)
        if status is not None:
            query = query.filter(JobApplication.status == status)
        if reviewed is not None:
            query = query.filter(JobApplication.reviewed == reviewed)
        if needs_review is not None:
            query = query.filter(JobApplication.needs_review == needs_review)
        return query.order_by(JobApplication.id.desc()).all()

    def mark_reviewed(self, application_id: int, reviewed: bool) -> Optional[JobApplication]:
        app = self._session.get(JobApplication, application_id)
        if app is None:
            return None
        app.reviewed = reviewed
        self._session.commit()
        self._session.refresh(app)
        return app
