import streamlit as st

from job_scraper.db import list_jobs_for_dashboard


# Load all saved job and AI rows from SQLite for display.
def _load_rows() -> list[dict]:
    return list_jobs_for_dashboard()


# Return sorted unique non-empty text values for filter widgets.
def _unique_text_values(values: list[str | None]) -> list[str]:
    unique_values = {
        value.strip()
        for value in values
        if isinstance(value, str) and value.strip()
    }
    return sorted(unique_values)


# Return sorted unique skills gathered across all saved jobs.
def _all_skills(rows: list[dict]) -> list[str]:
    skills: list[str] = []

    for row in rows:
        for skill in row.get("skills") or []:
            if isinstance(skill, str) and skill.strip():
                skills.append(skill.strip())

    return _unique_text_values(skills)


# Check whether a saved job matches the currently selected dashboard filters.
def _matches_filters(
    row: dict,
    selected_sources: list[str],
    selected_companies: list[str],
    selected_locations: list[str],
    selected_role_families: list[str],
    selected_seniorities: list[str],
    selected_remote_types: list[str],
    selected_skills: list[str],
) -> bool:
    if selected_sources and row.get("source") not in selected_sources:
        return False

    if selected_companies and row.get("company") not in selected_companies:
        return False

    if selected_locations and row.get("location_raw") not in selected_locations:
        return False

    if selected_role_families and row.get("role_family") not in selected_role_families:
        return False

    if selected_seniorities and row.get("seniority") not in selected_seniorities:
        return False

    if selected_remote_types and row.get("remote_type") not in selected_remote_types:
        return False

    if selected_skills:
        row_skills = row.get("skills") or []
        if not any(skill in row_skills for skill in selected_skills):
            return False

    return True


# Render one saved job row in a readable card-like layout.
def _render_job_card(row: dict) -> None:
    st.subheader(row.get("title", "Untitled Job"))
    st.caption(f"{row.get('company', 'Unknown Company')} | {row.get('location_raw', 'Unknown Location')} | {row.get('source', 'Unknown Source')}")

    facts: list[str] = []

    if row.get("seniority"):
        facts.append(f"Seniority: {row['seniority']}")

    if row.get("role_family"):
        facts.append(f"Role Family: {row['role_family']}")

    if row.get("remote_type"):
        facts.append(f"Remote Type: {row['remote_type']}")

    if row.get("confidence") is not None:
        facts.append(f"Confidence: {row['confidence']:.2f}")

    if row.get("posted_raw"):
        facts.append(f"Posted: {row['posted_raw']}")

    if facts:
        st.write(" | ".join(facts))

    summary = row.get("summary")
    if summary:
        st.write(summary)

    skills = row.get("skills") or []
    if skills:
        st.write("Skills: " + ", ".join(skills))

    tags = row.get("tags") or []
    if tags:
        st.write("Tags: " + ", ".join(tags))

    st.markdown(f"[Open original job post]({row['url']})")

    with st.expander("Show parsed description"):
        st.write(row.get("description_text", ""))

    st.divider()


# Build and run the Streamlit dashboard UI.
def main() -> None:
    st.set_page_config(page_title="AI Job Scraper", layout="wide")

    st.title("AI Job Scraper Dashboard")
    st.caption("Browse scraped jobs, parsed fields, and local AI enrichment results.")

    rows = _load_rows()

    if not rows:
        st.warning("No jobs found yet. Run crawl, parse, and enrich first.")
        return

    source_options = _unique_text_values([row.get("source") for row in rows])
    company_options = _unique_text_values([row.get("company") for row in rows])
    location_options = _unique_text_values([row.get("location_raw") for row in rows])
    role_family_options = _unique_text_values([row.get("role_family") for row in rows])
    seniority_options = _unique_text_values([row.get("seniority") for row in rows])
    remote_type_options = _unique_text_values([row.get("remote_type") for row in rows])
    skill_options = _all_skills(rows)

    st.sidebar.header("Filters")
    selected_sources = st.sidebar.multiselect("Source", source_options)
    selected_companies = st.sidebar.multiselect("Company", company_options)
    selected_locations = st.sidebar.multiselect("Location", location_options)
    selected_role_families = st.sidebar.multiselect("Role Family", role_family_options)
    selected_seniorities = st.sidebar.multiselect("Seniority", seniority_options)
    selected_remote_types = st.sidebar.multiselect("Remote Type", remote_type_options)
    selected_skills = st.sidebar.multiselect("Skills", skill_options)

    filtered_rows = [
        row
        for row in rows
        if _matches_filters(
            row,
            selected_sources,
            selected_companies,
            selected_locations,
            selected_role_families,
            selected_seniorities,
            selected_remote_types,
            selected_skills,
        )
    ]

    st.metric("Jobs Shown", len(filtered_rows))

    if not filtered_rows:
        st.info("No jobs match the current filters.")
        return

    for row in filtered_rows:
        _render_job_card(row)


if __name__ == "__main__":
    main()
