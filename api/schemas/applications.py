import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ApplicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    site: str
    search_term: Optional[str] = None
    status: str
    applied_at: Optional[datetime.datetime] = None
    error_message: Optional[str] = None
    job_updated_at: Optional[str] = None
    employer_active_at: Optional[str] = None
    needs_review: bool
    reviewed: bool


class ApplicationUpdate(BaseModel):
    reviewed: bool
