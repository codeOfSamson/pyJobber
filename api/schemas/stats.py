import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class RunStatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_date: datetime.date
    search_term_used: Optional[str] = None
    total_applied: int
    total_failed: int
    total_skipped: int
