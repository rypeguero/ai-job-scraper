# AI Job Scraper

A Python job ingestion pipeline for public job posting sites. It collects raw job data from multiple providers, normalizes listings into a shared schema, enriches job descriptions with a local Ollama model, and displays the results in a Streamlit dashboard.

## What This Project Does

This project is a full local data pipeline for software job listings:

- ingest jobs from public job posting sites
- support both browser-based HTML sources and public JSON API sources
- save raw source data for debugging and repeatable parsing
- normalize jobs into a shared structured model
- store parsed and enriched jobs in SQLite
- enrich job descriptions with a local LLM through Ollama
- browse and filter results in a Streamlit dashboard
- run the full pipeline from a Typer CLI

## Why This Project Is Resume-Worthy

It demonstrates more than a one-off scraper script:

- browser automation
- API integration
- HTML parsing
- schema validation
- relational storage
- AI enrichment
- testing
- a small product interface

It also shows source-agnostic design by supporting multiple job providers through a shared pipeline.

## Tech Stack

- Python
- Playwright
- httpx
- BeautifulSoup
- Pydantic
- SQLite
- Ollama with `qwen3:8b`
- Typer
- Streamlit
- Pytest

## Pipeline

1. `crawl`  
   Save raw listing and detail data from a public job source.

2. `parse`  
   Convert raw source data into structured job records.

3. `enrich`  
   Use a local LLM to extract:
   - summary
   - seniority
   - role family
   - skills
   - remote type
   - salary mentioned
   - confidence

4. `dashboard`  
   Browse and filter saved jobs visually.

## Supported Source Types

The project is designed for public job posting sites and supports both:

- HTML sources scraped with Playwright
- API sources fetched with `httpx`

### Currently Wired Sources

- `greenhouse`  
  HTML-based public job board ingestion
- `lever`  
  API-based public postings ingestion
- `ashby`  
  API-based public postings ingestion

### Included but Not Active

- `weworkremotely`  
  kept as an example adapter, but not the primary live source because bot protection blocked scraping during testing
- `workable`  
  planned in the source registry, but not yet wired into the fetcher

## Project Structure

```text
job_scraper/
  cli.py
  config.py
  dashboard.py
  db.py
  enrich.py
  fetcher.py
  models.py
  parser.py
  prompts.py
  sources/
    ashby.py
    base.py
    greenhouse.py
    lever.py
    registry.py
    weworkremotely.py
tests/
  fixtures/
    greenhouse_detail.html
  test_db.py
  test_enrich.py
  test_parser.py
data/
  raw/
  jobs.db
README.md
requirements.txt
```

## How AI Is Used

AI is used for semantic enrichment, not for scraping.

Rule-based source adapters handle factual extraction and normalization:

- job URLs
- titles
- company names
- locations
- descriptions
- tags

The local model handles fuzzy interpretation:

- what kind of role it is
- what skills it implies
- what seniority it suggests
- whether it is remote, hybrid, or on-site
- whether salary information is mentioned

This separation makes the system easier to debug and more reliable.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install
ollama pull qwen3:8b
```

Make sure Ollama is running before you use the enrichment step.

## Run The Project

Initialize the database:

```powershell
.\.venv\Scripts\python.exe -m job_scraper.cli init-db
```

Example crawl commands:

```powershell
.\.venv\Scripts\python.exe -m job_scraper.cli crawl --source greenhouse --identifier greenhouse --max-jobs 8
.\.venv\Scripts\python.exe -m job_scraper.cli crawl --source lever --identifier welocalize --max-jobs 8
.\.venv\Scripts\python.exe -m job_scraper.cli crawl --source ashby --identifier ashby --max-jobs 8
```

Parse saved jobs for a source:

```powershell
.\.venv\Scripts\python.exe -m job_scraper.cli parse --source lever --limit 20
```

Enrich parsed jobs with AI:

```powershell
.\.venv\Scripts\python.exe -m job_scraper.cli enrich --source lever --limit 20
```

Launch the dashboard:

```powershell
.\.venv\Scripts\python.exe -m job_scraper.cli dashboard
```

## Run The Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Design Decisions

- Raw source data is saved before parsing.  
  Why: this makes debugging easier and avoids re-fetching during parser development.

- Each provider gets its own source adapter.  
  Why: public job sites vary a lot in structure and transport type.

- The source registry defines supported providers in one place.  
  Why: the CLI and dashboard should not hardcode source options independently.

- Both HTML and API sources feed the same normalized model.  
  Why: the rest of the pipeline should stay source-agnostic.

- SQLite is used instead of CSV.  
  Why: deduping, querying, and dashboard use are much easier.

- AI output is validated before storage.  
  Why: model output should be treated as untrusted until normalized.

## Future Improvements

- add more public job source adapters
- finish wiring `workable`
- add tests for API-based source adapters
- normalize posted dates into true date fields
- export results to CSV
- add ranking or matching for target roles
- let the dashboard trigger pipeline actions directly
- deploy the dashboard
