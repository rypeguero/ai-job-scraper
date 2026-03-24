import json
from typing import Any

import httpx

from job_scraper.config import settings
from job_scraper.db import list_jobs_for_enrichment, upsert_ai_insights
from job_scraper.models import AIJobInsights, ParsedJob
from job_scraper.prompts import build_job_enrichment_prompt


# Call the local Ollama server and return the model's raw JSON text.
def _call_ollama(prompt: str) -> str:
    response = httpx.post(
        "http://127.0.0.1:11434/api/generate",
        json={
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0,
            },
        },
        timeout=180.0,
    )
    response.raise_for_status()

    payload = response.json()
    raw_text = payload.get("response", "")
    if not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("Ollama returned an empty response.")

    return raw_text.strip()


# Remove markdown code fences in case the model wraps its JSON output.
def _strip_code_fences(text: str) -> str:
    cleaned_text = text.strip()
    if not cleaned_text.startswith("```"):
        return cleaned_text

    lines = cleaned_text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]

    return "\n".join(lines).strip()


# Parse the model response into a Python dictionary.
def _parse_json_response(raw_response: str) -> dict[str, Any]:
    cleaned_response = _strip_code_fences(raw_response)
    parsed = json.loads(cleaned_response)

    if not isinstance(parsed, dict):
        raise ValueError("Model response was not a JSON object.")

    return parsed


# Convert a model value into a cleaned string with a safe default.
def _as_clean_text(value: Any, default: str) -> str:
    if isinstance(value, str):
        cleaned_value = value.strip()
        if cleaned_value:
            return cleaned_value

    return default


# Remove duplicate text values while keeping the original order stable.
def _unique_text_list(values: list[str]) -> list[str]:
    unique_values: list[str] = []
    seen: set[str] = set()

    for value in values:
        cleaned_value = value.strip()
        if not cleaned_value:
            continue

        lowered_value = cleaned_value.lower()
        if lowered_value in seen:
            continue

        seen.add(lowered_value)
        unique_values.append(cleaned_value)

    return unique_values


# Normalize the model's skills field into a clean list of strings.
def _coerce_skills(value: Any) -> list[str]:
    if isinstance(value, str):
        raw_skills = [part.strip() for part in value.split(",")]
        return _unique_text_list(raw_skills)

    if isinstance(value, list):
        raw_skills = [str(item).strip() for item in value if str(item).strip()]
        return _unique_text_list(raw_skills)

    return []


# Normalize the model's truthy or falsy value into a real boolean.
def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        lowered_value = value.strip().lower()
        if lowered_value in {"true", "yes", "1"}:
            return True
        if lowered_value in {"false", "no", "0"}:
            return False

    return False


# Normalize the confidence score into the 0 to 1 range expected by our schema.
def _coerce_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0

    if confidence > 1.0 and confidence <= 100.0:
        confidence = confidence / 100.0

    if confidence < 0.0:
        return 0.0

    if confidence > 1.0:
        return 1.0

    return confidence


# Run the local model for one parsed job and validate the structured result.
def _build_ai_insights(job: ParsedJob) -> AIJobInsights:
    prompt = build_job_enrichment_prompt(job)
    raw_response = _call_ollama(prompt)
    data = _parse_json_response(raw_response)

    return AIJobInsights(
        job_url=job.url,
        summary=_as_clean_text(data.get("summary"), "Summary not provided."),
        seniority=_as_clean_text(data.get("seniority"), "Unknown"),
        role_family=_as_clean_text(data.get("role_family"), "Other"),
        skills=_coerce_skills(data.get("skills")),
        remote_type=_as_clean_text(data.get("remote_type"), "Unknown"),
        salary_mentioned=_coerce_bool(data.get("salary_mentioned")),
        confidence=_coerce_confidence(data.get("confidence")),
    )


# Enrich parsed jobs with AI and save the validated results into SQLite.
def enrich_saved_jobs(source_name: str | None = None, limit: int | None = None) -> list[AIJobInsights]:
    jobs = list_jobs_for_enrichment()

    if source_name is not None:
        jobs = [job for job in jobs if job.source == source_name]

    if limit is not None:
        jobs = jobs[:limit]

    saved_insights: list[AIJobInsights] = []

    for job in jobs:
        try:
            ai_insights = _build_ai_insights(job)
        except Exception as error:
            print(f"Skipping AI enrichment for {job.url}: {error}")
            continue

        upsert_ai_insights(ai_insights)
        saved_insights.append(ai_insights)

    return saved_insights
