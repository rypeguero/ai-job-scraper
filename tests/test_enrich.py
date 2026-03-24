import json
from types import SimpleNamespace

import job_scraper.db as db_module
import job_scraper.enrich as enrich_module
from job_scraper.models import ParsedJob


# Point the database module at a temporary SQLite file for isolated tests.
def _use_temp_database(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        db_module,
        "settings",
        SimpleNamespace(database_path=tmp_path / "test_jobs.db"),
    )


# Return a stable fake model response so enrichment tests do not depend on Ollama.
def _fake_ollama_response(prompt: str) -> str:
    return json.dumps(
        {
            "summary": "This role manages customer relationships and improves product adoption.",
            "seniority": "Mid",
            "role_family": "Customer Success",
            "skills": ["Salesforce", "Communication", "Product Knowledge"],
            "remote_type": "Remote",
            "salary_mentioned": False,
            "confidence": 0.91,
        }
    )


# Confirm AI enrichment saves validated insights for a parsed job.
def test_enrich_saved_jobs_writes_ai_insights(monkeypatch, tmp_path) -> None:
    _use_temp_database(monkeypatch, tmp_path)
    db_module.init_db()

    parsed_job = ParsedJob(
        url="https://example.com/jobs/1",
        source="greenhouse",
        title="Customer Success Manager",
        company="Example Co",
        location_raw="Remote",
        posted_raw="2026-03-24",
        description_text="Use Salesforce and communication skills to support customers.",
        tags=["Customer Success"],
    )

    db_module.upsert_job(parsed_job)
    monkeypatch.setattr(enrich_module, "_call_ollama", _fake_ollama_response)

    results = enrich_module.enrich_saved_jobs(source_name="greenhouse", limit=1)
    rows = db_module.list_jobs_for_dashboard()

    assert len(results) == 1
    assert results[0].role_family == "Customer Success"
    assert results[0].remote_type == "Remote"
    assert rows[0]["summary"] == "This role manages customer relationships and improves product adoption."
    assert "Salesforce" in rows[0]["skills"]
