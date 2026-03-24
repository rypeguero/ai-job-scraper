from abc import ABC, abstractmethod
from typing import Any

from job_scraper.models import ParsedJob

# Define the required methods every website-specific scraper must implement to be compatible with the rest of the system.
class BaseSource(ABC):
    @abstractmethod
    def get_source_name(self) -> str:
        pass

    @abstractmethod
    def get_start_url(self) -> str:
        pass

    @abstractmethod
    def collect_job_links(self, page: Any) -> list[str]:
        pass

    @abstractmethod
    def parse_job_detail(self, html: str, url: str) -> ParsedJob:
        pass
