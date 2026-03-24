from types import SimpleNamespace

import job_scraper.db as db_module
from job_scraper.models import ParsedJob


# Point the database module at a temporary SQLite file for isolated tests.
def _use_temp_database(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        db_module,
        "settings",
        SimpleNamespace(database_path=tmp_path / "test_jobs.db"),
    )


# Confirm upsert_job updates an existing row instead of inserting a duplicate.
def test_upsert_job_updates_existing_row(monkeypatch, tmp_path) -> None:
    _use_temp_database(monkeypatch, tmp_path)
    db_module.init_db()

    first_job = ParsedJob(
        url="https://example.com/jobs/1",
        source="greenhouse",
        title="Customer Success Manager",
        company="Example Co",
        location_raw="Remote",
        posted_raw="2026-03-24",
        description_text="First version of the job description.",
        tags=["Customer Success"],
    )

    updated_job = ParsedJob(
        url="https://example.com/jobs/1",
        source="greenhouse",
        title="Senior Customer Success Manager",
        company="Example Co",
        location_raw="Remote",
        posted_raw="2026-03-24",
        description_text="Updated version of the job description.",
        tags=["Customer Success", "Leadership"],
    )

    db_module.upsert_job(first_job)
    db_module.upsert_job(updated_job)

    with db_module.get_connection() as connection:
        row_count = connection.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        saved_title = connection.execute(
            "SELECT title FROM jobs WHERE url = ?",
            (first_job.url,),
        ).fetchone()[0]

    assert row_count == 1
    assert saved_title == "Senior Customer Success Manager"
