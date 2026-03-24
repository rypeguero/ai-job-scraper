from job_scraper.models import ParsedJob


# Build the exact instruction we send to the local model for job enrichment.
def build_job_enrichment_prompt(job: ParsedJob) -> str:
    tag_text = ", ".join(job.tags) if job.tags else "None"

    return f"""
You extract structured insights from job postings.

Return valid JSON only.
Do not include markdown.
Do not include code fences.
Do not include any explanation outside the JSON.

Use exactly these keys:
- summary
- seniority
- role_family
- skills
- remote_type
- salary_mentioned
- confidence

Rules:
- summary: 1 or 2 sentences, plain English, concise.
- seniority: choose one of Internship, Junior, Mid, Senior, Staff, Lead, Manager, Director, Executive, Unknown.
- role_family: choose one of Engineering, Data, Design, Product, Sales, Customer Success, Marketing, Operations, People, Finance, Legal, Security, IT, Other.
- skills: return a JSON array of concrete skills or tools mentioned or strongly implied by the job.
- remote_type: choose one of Remote, Hybrid, On-site, Unknown.
- salary_mentioned: true if compensation is explicitly mentioned, otherwise false.
- confidence: a number between 0 and 1.

Job title: {job.title}
Company: {job.company}
Location: {job.location_raw}
Source tags: {tag_text}

Job description:
{job.description_text}
""".strip()
