from pathlib import Path
import json
from typing import Any
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from job_scraper.models import ParsedJob
from job_scraper.sources.base import BaseSource, RawSourceDocument

DEFAULT_JOB_BOARD_NAME = "ashby"


# Implement the source rules for Ashby's public job postings API.
class AshbySource(BaseSource):
    # Store the Ashby job board name so one adapter can target any Ashby board.
    def __init__(self, job_board_name: str = DEFAULT_JOB_BOARD_NAME) -> None:
        self.job_board_name = job_board_name.strip() or DEFAULT_JOB_BOARD_NAME

    # Return the internal source name used across the project.
    def get_source_name(self) -> str:
        return "ashby"

    # Return the public Ashby job postings API URL for the selected board.
    def get_start_url(self) -> str:
        return f"https://api.ashbyhq.com/posting-api/job-board/{self.job_board_name}?includeCompensation=true"

    # Fetch the raw JSON payload from Ashby's public job postings API.
    def fetch_listing_payload(self, identifier: str | None = None) -> str:
        response = httpx.get(self.get_start_url(), timeout=30.0)
        response.raise_for_status()
        return response.text

    # Split one Ashby API response into one raw document per listed job posting.
    def extract_job_documents(self, payload: str) -> list[RawSourceDocument]:
        items = _load_payload_jobs(payload)
        documents: list[RawSourceDocument] = []

        for item in items:
            if not _is_public_job(item):
                continue

            job_url = _extract_job_url(item, self.job_board_name)
            documents.append(
                RawSourceDocument(
                    url=job_url,
                    content=json.dumps(item),
                )
            )

        return documents

    # Parse one raw Ashby job document into the shared ParsedJob model.
    def parse_job_detail(self, html: str, url: str) -> ParsedJob:
        data = json.loads(html)

        title = _clean_text(str(data.get("title", "Unknown Title"))) or "Unknown Title"
        company = _extract_company_name(data, url, self.job_board_name)
        location_raw = _extract_location(data)
        posted_raw = _extract_posted_raw(data)
        description_text = _extract_description_text(data)
        tags = _extract_tags(data)

        return ParsedJob(
            url=url,
            source=self.get_source_name(),
            title=title,
            company=company,
            location_raw=location_raw,
            posted_raw=posted_raw,
            description_text=description_text,
            tags=tags,
        )


# Parse the Ashby API response and return the job posting objects.
def _load_payload_jobs(payload: str) -> list[dict[str, Any]]:
    parsed = json.loads(payload)

    if not isinstance(parsed, dict):
        return []

    jobs = parsed.get("jobs")
    if not isinstance(jobs, list):
        return []

    return [item for item in jobs if isinstance(item, dict)]


# Keep only jobs that Ashby says should be listed publicly.
def _is_public_job(item: dict[str, Any]) -> bool:
    is_listed = item.get("isListed")
    if isinstance(is_listed, bool):
        return is_listed

    return True


# Extract the best public URL for an Ashby job posting.
def _extract_job_url(item: dict[str, Any], fallback_board_name: str) -> str:
    job_url = item.get("jobUrl")
    if isinstance(job_url, str) and job_url.strip():
        return job_url.strip()

    apply_url = item.get("applyUrl")
    if isinstance(apply_url, str) and apply_url.strip():
        return apply_url.strip()

    title = str(item.get("title", "")).strip().replace(" ", "-").lower()
    if title:
        return f"https://jobs.ashbyhq.com/{fallback_board_name}/{title}"

    return f"https://jobs.ashbyhq.com/{fallback_board_name}"


# Convert a board slug into a readable company-like display name.
def _board_to_company_name(board_name: str) -> str:
    cleaned_board = board_name.replace("-", " ").replace("_", " ").strip()
    if not cleaned_board:
        return "Unknown Company"

    return cleaned_board.title()


# Extract the company name from the public job URL if possible.
def _extract_company_name(data: dict[str, Any], url: str, fallback_board_name: str) -> str:
    job_url = data.get("jobUrl")
    candidate_url = job_url if isinstance(job_url, str) and job_url.strip() else url

    parsed = urlparse(candidate_url)
    if parsed.netloc == "jobs.ashbyhq.com":
        parts = [part for part in parsed.path.split("/") if part]
        if parts:
            return _board_to_company_name(parts[0])

    return _board_to_company_name(fallback_board_name)


# Normalize messy whitespace into readable text.
def _clean_text(text: str) -> str:
    normalized_lines: list[str] = []

    for line in text.splitlines():
        cleaned_line = " ".join(line.split()).strip()
        if cleaned_line:
            normalized_lines.append(cleaned_line)

    return "\n".join(normalized_lines)


# Build the best available location text from Ashby's location fields.
def _extract_location(data: dict[str, Any]) -> str:
    location = data.get("location")
    if isinstance(location, str) and location.strip():
        return _clean_text(location)

    address = data.get("address")
    if isinstance(address, dict):
        postal_address = address.get("postalAddress")
        if isinstance(postal_address, dict):
            parts = [
                postal_address.get("addressLocality"),
                postal_address.get("addressRegion"),
                postal_address.get("addressCountry"),
            ]
            cleaned_parts = [_clean_text(str(part)) for part in parts if part]
            if cleaned_parts:
                return ", ".join(cleaned_parts)

    is_remote = data.get("isRemote")
    if is_remote is True:
        return "Remote"

    return "Unknown Location"


# Extract the best available published date signal from the Ashby payload.
def _extract_posted_raw(data: dict[str, Any]) -> str:
    published_at = data.get("publishedAt")
    if isinstance(published_at, str) and published_at.strip():
        return _clean_text(published_at)

    return "Unknown Posted Date"


# Build a readable description from Ashby's plaintext or HTML fields.
def _extract_description_text(data: dict[str, Any]) -> str:
    description_plain = data.get("descriptionPlain")
    if isinstance(description_plain, str) and description_plain.strip():
        cleaned_value = _clean_text(description_plain)
        if cleaned_value:
            return cleaned_value

    description_html = data.get("descriptionHtml")
    if isinstance(description_html, str) and description_html.strip():
        soup = BeautifulSoup(description_html, "html.parser")
        cleaned_value = _clean_text(soup.get_text("\n", strip=True))
        if cleaned_value:
            return cleaned_value

    return "Description not found."


# Extract lightweight tags from Ashby's structured category fields.
def _extract_tags(data: dict[str, Any]) -> list[str]:
    tags: list[str] = []

    for key in ["department", "team", "employmentType", "workplaceType", "location"]:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            tags.append(_clean_text(value))

    secondary_locations = data.get("secondaryLocations")
    if isinstance(secondary_locations, list):
        for item in secondary_locations:
            if not isinstance(item, dict):
                continue

            location = item.get("location")
            if isinstance(location, str) and location.strip():
                tags.append(_clean_text(location))

    compensation = data.get("compensation")
    if isinstance(compensation, dict):
        summary = compensation.get("compensationTierSummary")
        if isinstance(summary, str) and summary.strip():
            tags.append(_clean_text(summary))

    return _unique_preserving_order(tags)


# Remove duplicates while keeping the original order stable.
def _unique_preserving_order(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized_value = value.strip()
        if not normalized_value:
            continue

        lowered_value = normalized_value.lower()
        if lowered_value in seen:
            continue

        seen.add(lowered_value)
        unique_values.append(normalized_value)

    return unique_values
