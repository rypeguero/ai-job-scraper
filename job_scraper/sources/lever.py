from datetime import datetime, timezone
import json
from typing import Any
from urllib.parse import urlparse

import httpx

from job_scraper.models import ParsedJob
from job_scraper.sources.base import BaseSource, RawSourceDocument

DEFAULT_SITE = "lever"


# Implement the source rules for Lever's public postings API.
class LeverSource(BaseSource):
    # Store the Lever site name so one adapter can target any Lever board.
    def __init__(self, site: str = DEFAULT_SITE) -> None:
        self.site = site.strip() or DEFAULT_SITE

    # Return the internal source name used across the project.
    def get_source_name(self) -> str:
        return "lever"

    # Return the public Lever postings API URL for the selected site.
    def get_start_url(self) -> str:
        return f"https://api.lever.co/v0/postings/{self.site}?mode=json"

    # Fetch the raw JSON payload from Lever's public postings API.
    def fetch_listing_payload(self, identifier: str | None = None) -> str:
        response = httpx.get(self.get_start_url(), timeout=30.0)
        response.raise_for_status()
        return response.text

    # Split one Lever API response into one raw document per job posting.
    def extract_job_documents(self, payload: str) -> list[RawSourceDocument]:
        items = _load_payload_items(payload)
        documents: list[RawSourceDocument] = []

        for item in items:
            job_url = _extract_job_url(item, self.site)
            documents.append(
                RawSourceDocument(
                    url=job_url,
                    content=json.dumps(item),
                )
            )

        return documents

    # Parse one raw Lever job document into the shared ParsedJob model.
    def parse_job_detail(self, html: str, url: str) -> ParsedJob:
        data = json.loads(html)

        title = _clean_text(str(data.get("text", "Unknown Title"))) or "Unknown Title"
        company = _extract_company_name(data, url, self.site)
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


# Parse the Lever API response and return the job posting objects.
def _load_payload_items(payload: str) -> list[dict[str, Any]]:
    parsed = json.loads(payload)

    if not isinstance(parsed, list):
        return []

    return [item for item in parsed if isinstance(item, dict)]


# Extract the best public URL for a Lever job posting.
def _extract_job_url(item: dict[str, Any], fallback_site: str) -> str:
    hosted_url = item.get("hostedUrl")
    if isinstance(hosted_url, str) and hosted_url.strip():
        return hosted_url.strip()

    apply_url = item.get("applyUrl")
    if isinstance(apply_url, str) and apply_url.strip():
        return apply_url.strip()

    posting_id = item.get("id")
    if isinstance(posting_id, str) and posting_id.strip():
        return f"https://jobs.lever.co/{fallback_site}/{posting_id.strip()}"

    return f"https://jobs.lever.co/{fallback_site}"


# Convert a site slug into a readable company-like display name.
def _site_to_company_name(site: str) -> str:
    cleaned_site = site.replace("-", " ").replace("_", " ").strip()
    if not cleaned_site:
        return "Unknown Company"

    return cleaned_site.title()


# Extract the company name from the public job URL if possible.
def _extract_company_name(data: dict[str, Any], url: str, fallback_site: str) -> str:
    hosted_url = data.get("hostedUrl")
    candidate_url = hosted_url if isinstance(hosted_url, str) and hosted_url.strip() else url

    parsed = urlparse(candidate_url)
    if parsed.netloc == "jobs.lever.co":
        parts = [part for part in parsed.path.split("/") if part]
        if parts:
            return _site_to_company_name(parts[0])

    return _site_to_company_name(fallback_site)


# Normalize messy whitespace into readable text.
def _clean_text(text: str) -> str:
    normalized_lines: list[str] = []

    for line in text.splitlines():
        cleaned_line = " ".join(line.split()).strip()
        if cleaned_line:
            normalized_lines.append(cleaned_line)

    return "\n".join(normalized_lines)


# Extract the main location text from Lever categories.
def _extract_location(data: dict[str, Any]) -> str:
    categories = data.get("categories")
    if isinstance(categories, dict):
        location = categories.get("location")
        if isinstance(location, str) and location.strip():
            return _clean_text(location)

    return "Unknown Location"


# Format a numeric timestamp from Lever into an ISO-style date string.
def _format_timestamp(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return ""

    timestamp = float(value)

    if timestamp > 10_000_000_000:
        timestamp = timestamp / 1000.0

    return datetime.fromtimestamp(timestamp, tz=timezone.utc).date().isoformat()


# Extract the best available posted-date signal from the Lever payload.
def _extract_posted_raw(data: dict[str, Any]) -> str:
    for key in ["createdAt", "updatedAt"]:
        formatted_value = _format_timestamp(data.get(key))
        if formatted_value:
            return formatted_value

    return "Unknown Posted Date"


# Build a readable description from the plaintext fields Lever provides.
def _extract_description_text(data: dict[str, Any]) -> str:
    for key in ["descriptionPlain", "openingPlain", "descriptionBodyPlain", "additionalPlain"]:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            cleaned_value = _clean_text(value)
            if cleaned_value:
                return cleaned_value

    description = data.get("description")
    if isinstance(description, str) and description.strip():
        return _clean_text(description)

    return "Description not found."


# Extract lightweight tags from Lever category fields.
def _extract_tags(data: dict[str, Any]) -> list[str]:
    tags: list[str] = []

    categories = data.get("categories")
    if isinstance(categories, dict):
        for key in ["commitment", "team", "department", "level", "location"]:
            value = categories.get(key)
            if isinstance(value, str) and value.strip():
                tags.append(_clean_text(value))

        all_locations = categories.get("allLocations")
        if isinstance(all_locations, list):
            for location in all_locations:
                if isinstance(location, str) and location.strip():
                    tags.append(_clean_text(location))

    workplace_type = data.get("workplaceType")
    if isinstance(workplace_type, str) and workplace_type.strip():
        tags.append(_clean_text(workplace_type))

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
