from pathlib import Path
import subprocess
import sys

import typer

from job_scraper.db import init_db
from job_scraper.enrich import enrich_saved_jobs
from job_scraper.fetcher import crawl_source
from job_scraper.parser import parse_saved_jobs

app = typer.Typer(help="Run the job scraper pipeline one stage at a time.")


# Create the SQLite tables before running the scraper pipeline.
@app.command("init-db")
def init_db_command() -> None:
    init_db()
    typer.echo("Database initialized.")


# Crawl a source website and save raw listing and detail HTML pages.
@app.command("crawl")
def crawl_command(
    source: str | None = typer.Option(None, "--source", help="Source adapter name, like greenhouse."),
    identifier: str | None = typer.Option(None, "--identifier", help="Source-specific value, like a Greenhouse board token."),
    max_jobs: int | None = typer.Option(None, "--max-jobs", help="Maximum number of jobs to fetch."),
) -> None:
    links = crawl_source(source_name=source, identifier=identifier, max_jobs=max_jobs)

    typer.echo(f"Crawled {len(links)} job links.")
    for link in links:
        typer.echo(link)


# Parse saved raw HTML pages into structured job records in SQLite.
@app.command("parse")
def parse_command(
    source: str | None = typer.Option(None, "--source", help="Source adapter name, like greenhouse."),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of saved pages to parse."),
) -> None:
    jobs = parse_saved_jobs(source_name=source, limit=limit)

    typer.echo(f"Parsed {len(jobs)} jobs.")
    for job in jobs:
        typer.echo(f"{job.title} | {job.company} | {job.location_raw}")


# Enrich parsed jobs with AI and save the structured insights in SQLite.
@app.command("enrich")
def enrich_command(
    source: str | None = typer.Option(None, "--source", help="Source adapter name, like greenhouse."),
    limit: int | None = typer.Option(None, "--limit", help="Maximum number of jobs to enrich."),
) -> None:
    insights = enrich_saved_jobs(source_name=source, limit=limit)

    typer.echo(f"Enriched {len(insights)} jobs.")
    for insight in insights:
        typer.echo(f"{insight.role_family} | {insight.remote_type} | {insight.job_url}")


# Launch the Streamlit dashboard so we can browse saved jobs visually.
@app.command("dashboard")
def dashboard_command() -> None:
    dashboard_path = Path(__file__).resolve().parent / "dashboard.py"
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard_path)], check=True)


# Start the CLI app when this file is run as a module.
def main() -> None:
    app()


if __name__ == "__main__":
    main()
