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
from job_scraper.sources.weworkremotely import WeWorkRemotelySource


# Return the correct website adapter based on the selected source name.
def get_source_adapter(source_name: str | None = None) -> BaseSource:
    selected_source = source_name or settings.default_source

    if selected_source == "greenhouse":
        return GreenhouseSource()

    if selected_source == "weworkremotely":
        return WeWorkRemotelySource()

    raise ValueError(f"Unsupported source: {selected_source}")


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


# Build a stable HTML filename so repeated crawls update the same saved page.
def _build_raw_file_path(source_name: str, page_type: str, url: str) -> Path:
    url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()[:12]
    slug = _slug_from_url(url)
    filename = f"{source_name}__{slug}__{url_hash}.html"
    return _get_raw_folder(page_type) / filename


# Save downloaded HTML both on disk and in SQLite so later steps can reuse it.
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


# Raise a clear error when the fetched HTML is a bot-check page instead of real content.
def _ensure_not_blocked(html: str, url: str) -> None:
    block_reason = _find_block_reason(html)
    if block_reason is None:
        return

    raise RuntimeError(f"{block_reason} URL: {url}")


# Open the source website, collect job links, and save raw listing and detail pages.
def crawl_source(source_name: str | None = None, max_jobs: int | None = None) -> list[str]:
    source = get_source_adapter(source_name)
    job_limit = settings.max_jobs if max_jobs is None else max_jobs
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
