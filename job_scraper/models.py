from datetime import datetime

from pydantic import BaseModel, Field

# Represent a job link found on a listings page before we know the full details.
class JobSeed(BaseModel):
    url: str
    source: str
    job_id_hint: str | None = None

# Represent a raw downloaded page exactly as it was fetched from the website.
class RawJobPage(BaseModel):
    url: str
    source: str
    page_type: str
    html: str
    fetched_at: datetime
    file_path: str

# Represent a cleaned and structured job after parsing the raw HTML.
class ParsedJob(BaseModel):
    url: str
    source: str
    title: str
    company: str
    location_raw: str
    posted_raw: str
    description_text: str
    tags: list[str] = Field(default_factory=list)

# Represent the AI-generated insights we extract from a parsed job description.
class AIJobInsights(BaseModel):
    job_url: str
    summary: str
    seniority: str
    role_family: str
    skills: list[str] = Field(default_factory=list)
    remote_type: str
    salary_mentioned: bool
    confidence: float = Field(ge=0.0, le=1.0)
