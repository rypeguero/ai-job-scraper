import json
import sqlite3
from typing import Any

from job_scraper.config import settings
from job_scraper.models import AIJobInsights, ParsedJob, RawJobPage

# Open the SQLite database and return rows in a dictionary-like format.
def get_connection() -> sqlite3.Connection:
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(settings.database_path))
    connection.row_factory = sqlite3.Row
    return connection

# Create the database tables the project needs if they do not exist yet.
def init_db() -> None:
    with get_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS raw_pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL,
                source TEXT NOT NULL,
                page_type TEXT NOT NULL,
                html TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(source, url, page_type)
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL UNIQUE,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location_raw TEXT NOT NULL,
                posted_raw TEXT NOT NULL,
                description_text TEXT NOT NULL,
                tags_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS ai_insights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_url TEXT NOT NULL UNIQUE,
                summary TEXT NOT NULL,
                seniority TEXT NOT NULL,
                role_family TEXT NOT NULL,
                skills_json TEXT NOT NULL,
                remote_type TEXT NOT NULL,
                salary_mentioned INTEGER NOT NULL,
                confidence REAL NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (job_url) REFERENCES jobs(url)
            )
            """
        )

# Save a raw downloaded page so we can debug parsing later without re-scraping.
def save_raw_page(raw_page: RawJobPage) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO raw_pages (
                url,
                source,
                page_type,
                html,
                fetched_at,
                file_path
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, url, page_type) DO UPDATE SET
                html = excluded.html,
                fetched_at = excluded.fetched_at,
                file_path = excluded.file_path
            """,
            (
                raw_page.url,
                raw_page.source,
                raw_page.page_type,
                raw_page.html,
                raw_page.fetched_at.isoformat(),
                raw_page.file_path,
            ),
        )

# Insert a parsed job into the database or update it if it already exists.
def upsert_job(parsed_job: ParsedJob) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                url,
                source,
                title,
                company,
                location_raw,
                posted_raw,
                description_text,
                tags_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                source = excluded.source,
                title = excluded.title,
                company = excluded.company,
                location_raw = excluded.location_raw,
                posted_raw = excluded.posted_raw,
                description_text = excluded.description_text,
                tags_json = excluded.tags_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                parsed_job.url,
                parsed_job.source,
                parsed_job.title,
                parsed_job.company,
                parsed_job.location_raw,
                parsed_job.posted_raw,
                parsed_job.description_text,
                json.dumps(parsed_job.tags),
            ),
        )

# Insert AI enrichment results or update them if they already exist for a job.
def upsert_ai_insights(ai_insights: AIJobInsights) -> None:
    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO ai_insights (
                job_url,
                summary,
                seniority,
                role_family,
                skills_json,
                remote_type,
                salary_mentioned,
                confidence
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_url) DO UPDATE SET
                summary = excluded.summary,
                seniority = excluded.seniority,
                role_family = excluded.role_family,
                skills_json = excluded.skills_json,
                remote_type = excluded.remote_type,
                salary_mentioned = excluded.salary_mentioned,
                confidence = excluded.confidence,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                ai_insights.job_url,
                ai_insights.summary,
                ai_insights.seniority,
                ai_insights.role_family,
                json.dumps(ai_insights.skills),
                ai_insights.remote_type,
                int(ai_insights.salary_mentioned),
                ai_insights.confidence,
            ),
        )

# Return jobs that have been parsed but do not yet have AI insights.
def list_jobs_for_enrichment(limit: int | None = None) -> list[ParsedJob]:
    query = """
        SELECT
            jobs.url,
            jobs.source,
            jobs.title,
            jobs.company,
            jobs.location_raw,
            jobs.posted_raw,
            jobs.description_text,
            jobs.tags_json
        FROM jobs
        LEFT JOIN ai_insights
            ON ai_insights.job_url = jobs.url
        WHERE ai_insights.job_url IS NULL
        ORDER BY jobs.id ASC
    """

    parameters: tuple[Any, ...] = ()
    if limit is not None:
        query += " LIMIT ?"
        parameters = (limit,)

    with get_connection() as connection:
        rows = connection.execute(query, parameters).fetchall()

    jobs: list[ParsedJob] = []
    for row in rows:
        jobs.append(
            ParsedJob(
                url=row["url"],
                source=row["source"],
                title=row["title"],
                company=row["company"],
                location_raw=row["location_raw"],
                posted_raw=row["posted_raw"],
                description_text=row["description_text"],
                tags=json.loads(row["tags_json"]),
            )
        )
    return jobs

# Return combined job and AI data in a format the dashboard can display easily.
def list_jobs_for_dashboard() -> list[dict[str, Any]]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT
                jobs.url,
                jobs.source,
                jobs.title,
                jobs.company,
                jobs.location_raw,
                jobs.posted_raw,
                jobs.description_text,
                jobs.tags_json,
                ai_insights.summary,
                ai_insights.seniority,
                ai_insights.role_family,
                ai_insights.skills_json,
                ai_insights.remote_type,
                ai_insights.salary_mentioned,
                ai_insights.confidence
            FROM jobs
            LEFT JOIN ai_insights
                ON ai_insights.job_url = jobs.url
            ORDER BY jobs.id DESC
            """
        ).fetchall()

    results: list[dict[str, Any]] = []
    for row in rows:
        results.append(
            {
                "url": row["url"],
                "source": row["source"],
                "title": row["title"],
                "company": row["company"],
                "location_raw": row["location_raw"],
                "posted_raw": row["posted_raw"],
                "description_text": row["description_text"],
                "tags": json.loads(row["tags_json"]),
                "summary": row["summary"],
                "seniority": row["seniority"],
                "role_family": row["role_family"],
                "skills": json.loads(row["skills_json"]) if row["skills_json"] else [],
                "remote_type": row["remote_type"],
                "salary_mentioned": bool(row["salary_mentioned"]) if row["salary_mentioned"] is not None else None,
                "confidence": row["confidence"],
            }
        )
    return results
