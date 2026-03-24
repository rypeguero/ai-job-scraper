import re
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from job_scraper.models import ParsedJob
from job_scraper.sources.base import BaseSource

DEFAULT_BOARD_TOKEN = "greenhouse"
GREENHOUSE_HOSTS = {"job-boards.greenhouse.io", "boards.greenhouse.io"}


# Implement the website-specific scraping rules for a public Greenhouse job board.
class GreenhouseSource(BaseSource):
     # Store the board token so one adapter can target any Greenhouse board.
    def __init__(self, board_token: str = DEFAULT_BOARD_TOKEN) -> None:
        self.board_token = board_token.strip() or DEFAULT_BOARD_TOKEN

    # Return the internal source name used across the project.
    def get_source_name(self) -> str:
        return "greenhouse"

    # Return the public Greenhouse board page where job links are listed.
        # Return the public Greenhouse board page where job links are listed.
    def get_start_url(self) -> str:
        return f"https://job-boards.greenhouse.io/embed/job_board?for={self.board_token}"

    # Collect job detail links from the board page and skip placeholder talent-pool posts.
    def collect_job_links(self, page: Any) -> list[str]:
        link_candidates = page.locator("a[href]").evaluate_all(
            """
            elements => elements.map(element => ({
                href: element.getAttribute('href'),
                text: (element.innerText || element.textContent || '').trim()
            }))
            """
        )

        links: list[str] = []
        seen: set[str] = set()

        for candidate in link_candidates:
            href = candidate.get("href")
            text = candidate.get("text", "")

            if not isinstance(href, str) or not href.strip():
                continue

            if _looks_like_placeholder_link_text(text):
                continue

            normalized_url = _normalize_greenhouse_job_url(self.get_start_url(), href, self.board_token)

            if not normalized_url:
                continue

            if normalized_url in seen:
                continue

            seen.add(normalized_url)
            links.append(normalized_url)

        return links

    # Parse one Greenhouse job page into the shared ParsedJob model.
    def parse_job_detail(self, html: str, url: str) -> ParsedJob:
        soup = BeautifulSoup(html, "html.parser")

        title = _extract_title(soup) or "Unknown Title"
        company = _extract_company(soup) or "Unknown Company"
        location_raw = _extract_location(soup, title) or "Unknown Location"
        posted_raw = _extract_posted_raw(soup) or "Unknown Posted Date"
        description_text = _extract_description_text(soup, title, company, location_raw) or "Description not found."
        tags = _extract_tags(soup)

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


# Detect generic talent-pool links so the crawler keeps only real job postings.
def _looks_like_placeholder_link_text(text: str) -> bool:
    normalized_text = " ".join(text.split()).strip().lower()
    normalized_text = normalized_text.replace("’", "'")
    normalized_text = normalized_text.replace("â€™", "'")

    return "don't see what you're looking for?" in normalized_text


# Turn a raw href into a canonical Greenhouse job detail URL or reject it if it is not a job page.
def _normalize_greenhouse_job_url(base_url: str, href: str, expected_board_token: str) -> str | None:
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

    absolute_url = urljoin(base_url, cleaned_href)
    parsed = urlparse(absolute_url)

    if parsed.netloc not in GREENHOUSE_HOSTS:
        return None

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 3:
        return None

    board_token, section_name, job_id = parts
    if board_token != expected_board_token:
        return None

    if section_name != "jobs":
        return None

    if not job_id.isdigit():
        return None

    clean_path = f"/{board_token}/{section_name}/{job_id}"
    return urlunparse((parsed.scheme, parsed.netloc, clean_path, "", "", ""))


# Normalize messy whitespace so parsed text is easier to read and compare.
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


# Extract the job title from the strongest visible or metadata sources.
def _extract_title(soup: BeautifulSoup) -> str:
    title = _first_text(soup, ["h1", "main h1", "article h1"])
    if title:
        return title

    og_title = soup.select_one("meta[property='og:title']")
    if og_title and og_title.get("content"):
        content = _clean_text(str(og_title["content"]))
        matched = re.search(r"Job Application for (.+?) at ", content)
        if matched:
            return _clean_text(matched.group(1))

    page_title = soup.find("title")
    if page_title:
        title_text = _clean_text(page_title.get_text(" ", strip=True))
        matched = re.search(r"Job Application for (.+?) at ", title_text)
        if matched:
            return _clean_text(matched.group(1))

    return ""


# Extract the company name from metadata first and visible HTML second.
def _extract_company(soup: BeautifulSoup) -> str:
    og_title = soup.select_one("meta[property='og:title']")
    if og_title and og_title.get("content"):
        content = _clean_text(str(og_title["content"]))
        matched = re.search(r" at (.+)$", content)
        if matched:
            return _clean_text(matched.group(1))

    page_title = soup.find("title")
    if page_title:
        title_text = _clean_text(page_title.get_text(" ", strip=True))
        matched = re.search(r" at (.+)$", title_text)
        if matched:
            return _clean_text(matched.group(1))

    return _first_text(
        soup,
        [
            "[data-testid='company']",
            ".company",
            ".company-name",
            "[class*='company']",
        ],
    )


# Extract the location from obvious location selectors or the header area near the title.
def _extract_location(soup: BeautifulSoup, title: str) -> str:
    location = _first_text(
        soup,
        [
            "[data-testid='location']",
            ".location",
            "span.location",
            "div.location",
            "[class*='location']",
        ],
    )
    if location:
        return location

    main_element = soup.select_one("main") or soup.body or soup
    main_text = _clean_text(main_element.get_text("\n", strip=True))
    lines = [line for line in main_text.split("\n") if line]

    for line in lines[:12]:
        lowered = line.lower()
        if line == title:
            continue
        if lowered in {"apply", "apply now", "back to jobs"}:
            continue
        if len(line) > 80:
            continue
        return line

    return ""


# Extract any visible posted-date text if the page exposes it.
def _extract_posted_raw(soup: BeautifulSoup) -> str:
    time_element = soup.find("time")
    if time_element is not None:
        datetime_value = time_element.get("datetime")
        if isinstance(datetime_value, str) and datetime_value.strip():
            return _clean_text(datetime_value)

        time_text = _clean_text(time_element.get_text(" ", strip=True))
        if time_text:
            return time_text

    page_text = _clean_text((soup.body or soup).get_text("\n", strip=True))
    for line in page_text.split("\n"):
        lowered = line.lower()
        if "posted" in lowered and len(line) <= 80:
            return line

    return ""


# Extract the job description and stop before the application form begins.
def _extract_description_text(soup: BeautifulSoup, title: str, company: str, location_raw: str) -> str:
    description_element = soup.select_one(".job__description")
    if description_element is not None:
        description_text = _clean_text(description_element.get_text(" ", strip=True))
        if description_text:
            return description_text

    main_element = soup.select_one("main") or soup.body or soup
    text = _clean_text(main_element.get_text("\n", strip=True))
    text = _truncate_before_markers(
        text,
        [
            "Apply for this job",
            "Submit application",
            "Create a Job Alert",
        ],
    )

    lines = [line for line in text.split("\n") if line]
    lines = _strip_leading_header_lines(lines, title, company, location_raw)

    cleaned_text = "\n".join(lines).strip()
    return cleaned_text


# Remove the application form and footer by cutting the text at known markers.
def _truncate_before_markers(text: str, markers: list[str]) -> str:
    cutoff_indexes = [text.find(marker) for marker in markers if marker in text]
    if not cutoff_indexes:
        return text

    cutoff = min(cutoff_indexes)
    return text[:cutoff].strip()


# Remove repeated header lines so the description starts with the actual job content.
def _strip_leading_header_lines(lines: list[str], title: str, company: str, location_raw: str) -> list[str]:
    skipped_values = {
        title.strip().lower(),
        company.strip().lower(),
        location_raw.strip().lower(),
        "apply",
        "apply now",
        "back to jobs",
    }

    cleaned_lines = list(lines)
    while cleaned_lines and cleaned_lines[0].strip().lower() in skipped_values:
        cleaned_lines.pop(0)

    return cleaned_lines


# Extract lightweight tags such as department or visible labels if the page exposes them.
def _extract_tags(soup: BeautifulSoup) -> list[str]:
    tags: list[str] = []

    for selector in [
        ".department",
        "[class*='department']",
        ".office",
        "[class*='office']",
        ".tag",
        "[class*='tag']",
    ]:
        for element in soup.select(selector):
            text = _clean_text(element.get_text(" ", strip=True))
            if text and len(text) <= 50:
                tags.append(text)

    return _unique_preserving_order(tags)


# Remove duplicate values while keeping the original order stable.
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
