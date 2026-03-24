import json
from typing import Any
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from job_scraper.models import ParsedJob
from job_scraper.sources.base import BaseSource


# Implement the website-specific scraping rules for We Work Remotely.
class WeWorkRemotelySource(BaseSource):
    # Return the internal source name used across the project.
    def get_source_name(self) -> str:
        return "weworkremotely"

    # Return the page where this scraper should begin collecting jobs.
    def get_start_url(self) -> str:
        return "https://weworkremotely.com/"

    # Collect job detail links from the listings page and normalize them to full URLs.
    def collect_job_links(self, page: Any) -> list[str]:
        hrefs = page.locator("a[href]").evaluate_all(
            "elements => elements.map(element => element.getAttribute('href')).filter(Boolean)"
        )

        links: list[str] = []
        seen: set[str] = set()

        for href in hrefs:
            absolute_url = _absolute_job_url(self.get_start_url(), href)
            if not absolute_url:
                continue

            if not _looks_like_job_detail_url(absolute_url):
                continue

            if absolute_url in seen:
                continue

            seen.add(absolute_url)
            links.append(absolute_url)

        return links

    # Parse one saved job detail page into the shared ParsedJob model.
    def parse_job_detail(self, html: str, url: str) -> ParsedJob:
        soup = BeautifulSoup(html, "html.parser")
        job_posting = _extract_job_posting_data(soup)

        title = _extract_title(soup, job_posting) or "Unknown Title"
        company = _extract_company(soup, job_posting) or "Unknown Company"
        location_raw = _extract_location(soup, job_posting) or "Unknown Location"
        posted_raw = _extract_posted_date(soup, job_posting) or "Unknown Posted Date"
        description_text = _extract_description_text(soup, job_posting) or "Description not found."
        tags = _extract_tags(soup, job_posting)

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


# Turn a relative href into an absolute URL and ignore unusable link types.
def _absolute_job_url(base_url: str, href: str) -> str | None:
    cleaned_href = href.strip()

    if not cleaned_href:
        return None

    if cleaned_href.startswith("#"):
        return None

    if cleaned_href.startswith("javascript:"):
        return None

    if cleaned_href.startswith("mailto:"):
        return None

    if cleaned_href.startswith("tel:"):
        return None

    return urljoin(base_url, cleaned_href)


# Keep only URLs that look like real We Work Remotely job detail pages.
def _looks_like_job_detail_url(url: str) -> bool:
    parsed = urlparse(url)

    if parsed.netloc not in {"weworkremotely.com", "www.weworkremotely.com"}:
        return False

    if parsed.query:
        return False

    path = parsed.path.rstrip("/")

    if not path.startswith("/remote-jobs/"):
        return False

    parts = [part for part in path.split("/") if part]
    if len(parts) != 2:
        return False

    slug = parts[-1]
    blocked_slugs = {"search", "apply", "company", "categories", "all"}

    return slug not in blocked_slugs


# Find JobPosting structured data if the page exposes JSON-LD metadata.
def _extract_job_posting_data(soup: BeautifulSoup) -> dict[str, Any] | None:
    for script in soup.find_all("script", type="application/ld+json"):
        raw_text = script.string or script.get_text(strip=True)
        if not raw_text:
            continue

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            continue

        for item in _flatten_json_ld(data):
            if _is_job_posting(item):
                return item

    return None


# Flatten JSON-LD so we can search normal objects and @graph objects the same way.
def _flatten_json_ld(data: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    if isinstance(data, list):
        for item in data:
            items.extend(_flatten_json_ld(item))
        return items

    if isinstance(data, dict):
        items.append(data)

        graph = data.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                items.extend(_flatten_json_ld(item))

    return items


# Check whether a JSON-LD object represents a job posting.
def _is_job_posting(item: dict[str, Any]) -> bool:
    type_value = item.get("@type")

    if isinstance(type_value, list):
        return "JobPosting" in type_value

    return type_value == "JobPosting"


# Normalize messy whitespace so parsed text is clean and readable.
def _clean_text(text: str) -> str:
    normalized_lines: list[str] = []

    for line in text.splitlines():
        cleaned_line = " ".join(line.split()).strip()
        if cleaned_line:
            normalized_lines.append(cleaned_line)

    return "\n".join(normalized_lines)


# Return the first non-empty text found from a list of CSS selectors.
def _first_text(soup: BeautifulSoup, selectors: list[str], separator: str = " ") -> str:
    for selector in selectors:
        element = soup.select_one(selector)
        if element is None:
            continue

        text = _clean_text(element.get_text(separator, strip=True))
        if text:
            return text

    return ""


# Extract the job title using structured data first and visible HTML second.
def _extract_title(soup: BeautifulSoup, job_posting: dict[str, Any] | None) -> str:
    if job_posting:
        title = job_posting.get("title")
        if isinstance(title, str) and title.strip():
            return _clean_text(title)

    title = _first_text(soup, ["h1", "main h1", "article h1"])
    if title:
        return title

    og_title = soup.select_one("meta[property='og:title']")
    if og_title and og_title.get("content"):
        return _clean_text(str(og_title["content"]))

    page_title = soup.find("title")
    if page_title:
        return _clean_text(page_title.get_text(" ", strip=True))

    return ""


# Extract the company name using structured data first and HTML fallbacks second.
def _extract_company(soup: BeautifulSoup, job_posting: dict[str, Any] | None) -> str:
    if job_posting:
        hiring_organization = job_posting.get("hiringOrganization")

        if isinstance(hiring_organization, dict):
            company_name = hiring_organization.get("name")
            if isinstance(company_name, str) and company_name.strip():
                return _clean_text(company_name)

        if isinstance(hiring_organization, str) and hiring_organization.strip():
            return _clean_text(hiring_organization)

    return _first_text(
        soup,
        [
            "[data-testid='company']",
            ".company",
            ".company-name",
            "span.company",
            "div.company",
            "main h2",
            "article h2",
        ],
    )


# Extract the location, preferring structured data when available.
def _extract_location(soup: BeautifulSoup, job_posting: dict[str, Any] | None) -> str:
    if job_posting:
        location = _extract_location_from_job_posting(job_posting)
        if location:
            return location

    return _first_text(
        soup,
        [
            "[data-testid='location']",
            ".location",
            ".location-and-remote",
            "span.location",
            "div.location",
            "[class*='location']",
        ],
    )


# Convert structured job location data into readable text.
def _extract_location_from_job_posting(job_posting: dict[str, Any]) -> str:
    job_location_type = job_posting.get("jobLocationType")
    if isinstance(job_location_type, str) and job_location_type.strip():
        if job_location_type.strip().upper() == "TELECOMMUTE":
            return "Remote"
        return _clean_text(job_location_type)

    job_location = job_posting.get("jobLocation")
    formatted_job_location = _format_location_value(job_location)
    if formatted_job_location:
        return formatted_job_location

    applicant_location = job_posting.get("applicantLocationRequirements")
    return _format_location_value(applicant_location)


# Convert nested structured location values into a single readable string.
def _format_location_value(value: Any) -> str:
    if isinstance(value, str) and value.strip():
        return _clean_text(value)

    if isinstance(value, list):
        parts = [_format_location_value(item) for item in value]
        cleaned_parts = [part for part in parts if part]
        return ", ".join(cleaned_parts)

    if isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, str) and name.strip():
            return _clean_text(name)

        address = value.get("address")
        if isinstance(address, dict):
            address_parts = [
                address.get("addressLocality"),
                address.get("addressRegion"),
                address.get("addressCountry"),
            ]
            cleaned_parts = [_clean_text(str(part)) for part in address_parts if part]
            return ", ".join(cleaned_parts)

    return ""


# Extract the posted date using structured data first and HTML fallbacks second.
def _extract_posted_date(soup: BeautifulSoup, job_posting: dict[str, Any] | None) -> str:
    if job_posting:
        date_posted = job_posting.get("datePosted")
        if isinstance(date_posted, str) and date_posted.strip():
            return _clean_text(date_posted)

    time_element = soup.find("time")
    if time_element is not None:
        datetime_value = time_element.get("datetime")
        if isinstance(datetime_value, str) and datetime_value.strip():
            return _clean_text(datetime_value)

        time_text = _clean_text(time_element.get_text(" ", strip=True))
        if time_text:
            return time_text

    return _first_text(
        soup,
        [
            "[data-testid='posted-date']",
            ".posted",
            ".date",
            "[class*='posted']",
            "[class*='date']",
        ],
    )


# Extract the full job description text and keep paragraph breaks readable.
def _extract_description_text(soup: BeautifulSoup, job_posting: dict[str, Any] | None) -> str:
    if job_posting:
        description = job_posting.get("description")
        if isinstance(description, str) and description.strip():
            description_soup = BeautifulSoup(description, "html.parser")
            description_text = _clean_text(description_soup.get_text("\n", strip=True))
            if description_text:
                return description_text

    for selector in [
        "[data-testid='job-description']",
        ".job-description",
        ".listing-container",
        ".listing-container__content",
        "article",
        "main",
    ]:
        element = soup.select_one(selector)
        if element is None:
            continue

        text = _clean_text(element.get_text("\n", strip=True))
        if text and len(text) >= 80:
            return text

    return _clean_text(soup.get_text("\n", strip=True))


# Extract visible tags or keywords and remove duplicates while keeping order.
def _extract_tags(soup: BeautifulSoup, job_posting: dict[str, Any] | None) -> list[str]:
    tags: list[str] = []

    if job_posting:
        keywords = job_posting.get("keywords")

        if isinstance(keywords, str):
            tags.extend(_split_keywords(keywords))

        if isinstance(keywords, list):
            for keyword in keywords:
                if isinstance(keyword, str) and keyword.strip():
                    tags.append(_clean_text(keyword))

    for selector in [".tag", ".listing-tag", "a[href*='term=']", "[class*='tag']"]:
        for element in soup.select(selector):
            text = _clean_text(element.get_text(" ", strip=True))
            if text and len(text) <= 50:
                tags.append(text)

    return _unique_preserving_order(tags)


# Split a comma-separated keyword string into clean tag values.
def _split_keywords(keywords: str) -> list[str]:
    return [_clean_text(part) for part in keywords.split(",") if _clean_text(part)]


# Remove duplicates while keeping the original order stable.
def _unique_preserving_order(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        normalized = value.strip()
        if not normalized:
            continue

        lowered = normalized.lower()
        if lowered in seen:
            continue

        seen.add(lowered)
        unique_values.append(normalized)

    return unique_values
