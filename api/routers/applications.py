from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.dependencies import get_current_user, get_db
from api.schemas.applications import ApplicationOut, ApplicationUpdate
from api.services.application_service import ApplicationService

router = APIRouter(prefix="/api/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    site: Optional[str] = None,
    status: Optional[str] = None,
    reviewed: Optional[bool] = None,
    needs_review: Optional[bool] = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    service = ApplicationService(db)
    return service.list_filtered(site=site, status=status, reviewed=reviewed, needs_review=needs_review)


@router.patch("/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    service = ApplicationService(db)
    updated = service.mark_reviewed(application_id, payload.reviewed)
    if updated is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return updated
