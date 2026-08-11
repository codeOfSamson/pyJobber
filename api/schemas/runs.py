from typing import List, Optional

from pydantic import BaseModel


class RunRequest(BaseModel):
    sites: Optional[List[str]] = None
    search_term: Optional[str] = None


class RunResponse(BaseModel):
    task_arn: str
