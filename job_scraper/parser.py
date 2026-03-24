from datetime import datetime

from job_scraper.db import get_connection, upsert_job
from job_scraper.fetcher import get_source_adapter
from job_scraper.models import ParsedJob, RawJobPage


# Load saved raw detail pages for one source from SQLite.
def _load_raw_detail_pages(source_name: str) -> list[RawJobPage]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                url,
                source,
                page_type,
                html,
                fetched_at,
                file_path
            FROM raw_pages
            WHERE source = ? AND page_type = 'detail'
            ORDER BY id ASC
            """,
            (source_name,),
        ).fetchall()

    raw_pages: list[RawJobPage] = []
    for row in rows:
        raw_pages.append(
            RawJobPage(
                url=row["url"],
                source=row["source"],
                page_type=row["page_type"],
                html=row["html"],
                fetched_at=datetime.fromisoformat(row["fetched_at"]),
                file_path=row["file_path"],
            )
        )

    return raw_pages


# Skip generic talent-pool posts so the database keeps only real jobs.
def _should_store_job(parsed_job: ParsedJob) -> bool:
    normalized_title = parsed_job.title.strip().lower()
    normalized_title = normalized_title.replace("’", "'")
    normalized_title = normalized_title.replace("â€™", "'")

    blocked_titles = {
        "don't see what you're looking for?",
    }

    return normalized_title not in blocked_titles


# Parse saved raw detail pages for one source and store the valid jobs in SQLite.
def parse_saved_jobs(source_name: str | None = None, limit: int | None = None) -> list[ParsedJob]:
    source = get_source_adapter(source_name)
    raw_pages = _load_raw_detail_pages(source.get_source_name())

    if limit is not None:
        raw_pages = raw_pages[:limit]

    parsed_jobs: list[ParsedJob] = []

    for raw_page in raw_pages:
        parsed_job = source.parse_job_detail(raw_page.html, raw_page.url)

        if not _should_store_job(parsed_job):
            continue

        upsert_job(parsed_job)
        parsed_jobs.append(parsed_job)

    return parsed_jobs
