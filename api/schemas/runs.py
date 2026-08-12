from typing import List, Literal, Optional

from pydantic import BaseModel


class RunRequest(BaseModel):
    sites: Optional[List[Literal["cakeresume", "104", "linkedin"]]] = None
    search_term: Optional[str] = None


class RunResponse(BaseModel):
    task_arn: str
