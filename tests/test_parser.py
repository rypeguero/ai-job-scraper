from pathlib import Path

from job_scraper.sources.greenhouse import GreenhouseSource


# Load the HTML fixture used by parser tests.
def _load_fixture_html() -> str:
    fixture_path = Path(__file__).parent / "fixtures" / "greenhouse_detail.html"
    return fixture_path.read_text(encoding="utf-8")


# Confirm the Greenhouse parser extracts the expected fields from fixture HTML.
def test_greenhouse_parser_extracts_expected_fields() -> None:
    source = GreenhouseSource()
    job = source.parse_job_detail(
        _load_fixture_html(),
        "https://job-boards.greenhouse.io/greenhouse/jobs/7705020",
    )

    assert job.source == "greenhouse"
    assert job.title == "Customer Success Manager, Mid-Market"
    assert job.company == "Greenhouse"
    assert job.location_raw == "Anywhere in Ireland"
    assert job.posted_raw == "2026-03-24"
    assert "drive adoption and retention" in job.description_text
    assert "Customer Success" in job.tags
