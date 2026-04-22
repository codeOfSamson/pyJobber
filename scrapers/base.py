from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class ApplyResult:
    status: str  # "applied" | "failed" | "skipped"
    error: Optional[str] = None
    job_updated_at: Optional[str] = None
    employer_active_at: Optional[str] = None
    screening_links: List[str] = field(default_factory=list)


class BaseScraper(ABC):
    @abstractmethod
    def login(self, page) -> None: ...

    @abstractmethod
    def collect_links(self, page, search_term: str, pages: int, remote_only: bool) -> list[str]: ...

    @abstractmethod
    def apply(self, page, url: str, resume_path: str, resume_text: str) -> ApplyResult: ...
