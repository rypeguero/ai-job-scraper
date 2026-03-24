# AI Job Scraper

A Python job scraper that crawls a public Greenhouse job board, stores raw and parsed job data in SQLite, enriches job descriptions with a local Ollama model, and displays the results in a Streamlit dashboard.

## What This Project Does

This project is a full local data pipeline:

- crawl public job listings with Playwright
- save raw HTML for debugging and repeatable parsing
- parse job pages into structured records with BeautifulSoup
- validate data with Pydantic models
- store everything in SQLite
- enrich jobs with a local LLM through Ollama
- browse results in a Streamlit dashboard
- run the whole flow from a Typer CLI

## Why This Project Is Resume-Worthy

It shows more than scraping. It demonstrates:

- browser automation
- HTML parsing
- schema validation
- relational storage
- AI enrichment
- testing
- a small product interface

That combination makes it stronger than a one-file scraper script.

## Tech Stack

- Python
- Playwright
- BeautifulSoup
- Pydantic
- SQLite
- Ollama with `qwen3:8b`
- Typer
- Streamlit
- Pytest

## Pipeline

1. `crawl`
   Save raw listing and detail HTML pages.

2. `parse`
   Convert raw HTML into structured job records.

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
    base.py
    greenhouse.py
    weworkremotely.py
tests/
  fixtures/
    greenhouse_detail.html
  test_db.py
```

## How AI Is Used

AI is used for semantic enrichment, not for scraping HTML.

Rule-based code handles the factual parts of the job page:
- links
- titles
- company names
- locations
- descriptions

The local model handles the fuzzy interpretation:
- what kind of role it is
- what skills it implies
- what seniority it suggests
- whether it is remote, hybrid, or on-site

This separation makes the system easier to debug and more reliable.

## Current Source

The default live source is `greenhouse`.

`weworkremotely` is still included as an example source adapter, but it is not the main live source because it returned bot-protection pages during testing.

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

```powershell
.\.venv\Scripts\python.exe -m job_scraper.cli init-db
.\.venv\Scripts\python.exe -m job_scraper.cli crawl --source greenhouse --max-jobs 8
.\.venv\Scripts\python.exe -m job_scraper.cli parse --source greenhouse
.\.venv\Scripts\python.exe -m job_scraper.cli enrich --source greenhouse --limit 20
.\.venv\Scripts\python.exe -m job_scraper.cli dashboard
```

## Run The Tests

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Design Decisions

- Raw HTML is saved before parsing.
  Why: this makes debugging easier and avoids re-scraping during parser development.

- Each source gets its own adapter file.
  Why: websites differ a lot, so source-specific logic should stay isolated.

- SQLite is used instead of CSV.
  Why: deduping, querying, and dashboard use are much easier.

- AI output is validated with Pydantic.
  Why: model output should be treated as untrusted until validated.

- The pipeline is split into crawl, parse, and enrich stages.
  Why: each stage has one responsibility, which makes the project easier to understand and maintain.

## Future Improvements

- add more source adapters
- normalize posted dates into real date values
- export results to CSV
- add search and ranking for target roles
- deploy the dashboard
 more source adapters
normalize posted dates into real date values
export results to CSV
add search and ranking for target roles
deploy the dashboard