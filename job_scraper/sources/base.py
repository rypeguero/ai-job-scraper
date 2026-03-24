from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from job_scraper.models import ParsedJob


# Represent one raw job document extracted from a source response.
@dataclass(frozen=True)
class RawSourceDocument:
    url: str
    content: str


# Define the shared methods every source adapter must support.
class BaseSource(ABC):
    # Return the internal source name used across the project.
    @abstractmethod
    def get_source_name(self) -> str:
        pass

    # Return the main listing URL or API URL for the source.
    @abstractmethod
    def get_start_url(self) -> str:
        pass

    # Collect job detail links from an HTML listing page.
    def collect_job_links(self, page: Any) -> list[str]:
        raise NotImplementedError(f"{self.get_source_name()} does not implement HTML link collection.")

    # Fetch the raw listing payload for an API-based source.
    def fetch_listing_payload(self, identifier: str | None = None) -> str:
        raise NotImplementedError(f"{self.get_source_name()} does not implement API payload fetching.")

    # Split one API response into individual raw job documents.
    def extract_job_documents(self, payload: str) -> list[RawSourceDocument]:
        raise NotImplementedError(f"{self.get_source_name()} does not implement API document extraction.")

    # Parse one raw job document into the shared ParsedJob model.
    @abstractmethod
    def parse_job_detail(self, html: str, url: str) -> ParsedJob:
        pass
