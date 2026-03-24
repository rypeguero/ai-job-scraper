from datetime import datetime, timezone
import hashlib
from pathlib import Path
import time
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from job_scraper.config import settings
from job_scraper.db import save_raw_page
from job_scraper.models import RawJobPage
from job_scraper.sources.base import BaseSource
from job_scraper.sources.greenhouse import GreenhouseSource
from job_scraper.sources.lever import LeverSource
from job_scraper.sources.registry import get_source_definition, list_enabled_source_names
from job_scraper.sources.weworkremotely import WeWorkRemotelySource
from job_scraper.sources.ashby import AshbySource



# Return the enabled source names that the current fetcher can actually run.
def list_available_source_names() -> list[str]:
    available_names: list[str] = []

    for source_name in list_enabled_source_names():
        if source_name in {"greenhouse", "weworkremotely", "lever", "ashby"}:
            available_names.append(source_name)

    return available_names


# Return the correct source adapter based on the selected source name and identifier.
def get_source_adapter(source_name: str | None = None, identifier: str | None = None) -> BaseSource:
    selected_source = source_name or settings.default_source
    definition = get_source_definition(selected_source)

    if not definition.is_enabled:
        raise ValueError(f"Source '{selected_source}' is currently disabled.")

    if selected_source == "greenhouse":
        selected_identifier = identifier or definition.identifier_placeholder
        return GreenhouseSource(selected_identifier)

    if selected_source == "weworkremotely":
        return WeWorkRemotelySource()

    if selected_source == "lever":
        selected_identifier = identifier or definition.identifier_placeholder
        return LeverSource(selected_identifier)

    if selected_source == "ashby":
        selected_identifier = identifier or definition.identifier_placeholder
        return AshbySource(selected_identifier)

    raise ValueError(f"No adapter class is registered for source '{selected_source}'.")


# Turn a URL path into a safe filename fragment we can store on disk.
def _slug_from_url(url: str) -> str:
    parsed = urlparse(url)
    raw_value = parsed.path.strip("/") or "home"
    safe_value = "".join(character if character.isalnum() else "_" for character in raw_value)
    safe_value = safe_value.strip("_")
    safe_value = safe_value[:80]
    return safe_value or "page"


# Return the correct raw HTML folder for listing pages versus detail pages.
def _get_raw_folder(page_type: str) -> Path:
    folder_name = "listings" if page_type == "listing" else "details"
    folder_path = settings.database_path.parent / "raw" / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path


# Build a stable raw file path so repeated crawls update the same saved page.
def _build_raw_file_path(source_name: str, page_type: str, url: str) -> Path:
    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()[:12]
    slug = _slug_from_url(url)
    filename = f"{source_name}__{slug}__{url_hash}.html"
    return _get_raw_folder(page_type) / filename


# Save raw source content both on disk and in SQLite so later steps can reuse it.
def _save_raw_html(source_name: str, page_type: str, url: str, html: str) -> RawJobPage:
    file_path = _build_raw_file_path(source_name, page_type, url)
    file_path.write_text(html, encoding="utf-8")

    raw_page = RawJobPage(
        url=url,
        source=source_name,
        page_type=page_type,
        html=html,
        fetched_at=datetime.now(timezone.utc),
        file_path=str(file_path),
    )

    save_raw_page(raw_page)
    return raw_page


# Return a readable reason only when the HTML strongly looks like a bot-protection page.
def _find_block_reason(html: str) -> str | None:
    lowered_html = html.lower()

    if "just a moment" in lowered_html:
        return "The page looks like a Cloudflare 'Just a moment' challenge."

    if "performing security verification" in lowered_html:
        return "The page is showing a security verification screen."

    if "enable javascript and cookies to continue" in lowered_html:
        return "The page is asking for a bot-protection verification step."

    if "cf-turnstile" in lowered_html and "challenge-platform" in lowered_html:
        return "The page includes a Cloudflare Turnstile challenge."

    if "captcha" in lowered_html and "verify you are human" in lowered_html:
        return "The page appears to be a CAPTCHA challenge."

    return None


# Raise a clear error when fetched HTML is a bot-check page instead of real content.
def _ensure_not_blocked(html: str, url: str) -> None:
    block_reason = _find_block_reason(html)
    if block_reason is None:
        return

    raise RuntimeError(f"{block_reason} URL: {url}")


# Crawl an HTML source with Playwright and save raw listing and detail pages.
def _crawl_html_source(source: BaseSource, job_limit: int) -> list[str]:
    start_url = source.get_start_url()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()

        try:
            page.goto(start_url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)

            listing_html = page.content()
            _save_raw_html(source.get_source_name(), "listing", start_url, listing_html)
            _ensure_not_blocked(listing_html, start_url)

            job_links = source.collect_job_links(page)
            selected_links = job_links[:job_limit]

            for job_url in selected_links:
                time.sleep(settings.request_delay_seconds)
                page.goto(job_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1500)

                detail_html = page.content()
                _save_raw_html(source.get_source_name(), "detail", job_url, detail_html)
                _ensure_not_blocked(detail_html, job_url)

        finally:
            browser.close()

    return selected_links


# Crawl an API source and save the listing payload plus one raw document per job.
def _crawl_api_source(source: BaseSource, identifier: str | None, job_limit: int) -> list[str]:
    listing_payload = source.fetch_listing_payload(identifier=identifier)
    _save_raw_html(source.get_source_name(), "listing", source.get_start_url(), listing_payload)

    documents = source.extract_job_documents(listing_payload)
    selected_documents = documents[:job_limit]

    for document in selected_documents:
        _save_raw_html(source.get_source_name(), "detail", document.url, document.content)

    return [document.url for document in selected_documents]


# Fetch jobs from the selected source and save the raw source data for later parsing.
def crawl_source(
    source_name: str | None = None,
    identifier: str | None = None,
    max_jobs: int | None = None,
) -> list[str]:
    selected_source = source_name or settings.default_source
    definition = get_source_definition(selected_source)
    source = get_source_adapter(selected_source, identifier=identifier)
    job_limit = settings.max_jobs if max_jobs is None else max_jobs

    if definition.transport_type == "html":
        return _crawl_html_source(source, job_limit)

    if definition.transport_type == "api":
        return _crawl_api_source(source, identifier=identifier, job_limit=job_limit)

    raise ValueError(f"Unsupported transport type: {definition.transport_type}")
