import streamlit as st

from job_scraper.db import list_jobs_for_dashboard
from job_scraper.sources.registry import get_source_definition, list_source_definitions


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


# Return all supported source names from the registry for the control panel.
def _supported_source_names() -> list[str]:
    return [definition.name for definition in list_source_definitions()]


# Build a ready-to-copy crawl command from the selected source settings.
def _build_crawl_command(source_name: str, identifier: str, max_jobs: int) -> str:
    command = f".\\.venv\\Scripts\\python.exe -m job_scraper.cli crawl --source {source_name}"

    if identifier.strip():
        command += f" --identifier {identifier.strip()}"

    command += f" --max-jobs {max_jobs}"
    return command


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
    st.caption(
        f"{row.get('company', 'Unknown Company')} | "
        f"{row.get('location_raw', 'Unknown Location')} | "
        f"{row.get('source', 'Unknown Source')}"
    )

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

    st.sidebar.header("Source Control Panel")

    supported_sources = _supported_source_names()
    selected_source_name = st.sidebar.selectbox("Supported Source", supported_sources)

    selected_definition = get_source_definition(selected_source_name)
    identifier_value = st.sidebar.text_input(
        selected_definition.identifier_label,
        value=selected_definition.identifier_placeholder,
        help=f"Source-specific value for {selected_definition.display_name}.",
    )
    max_jobs_value = st.sidebar.number_input("Max Jobs", min_value=1, max_value=100, value=10, step=1)

    st.sidebar.caption(f"Transport: {selected_definition.transport_type}")
    st.sidebar.caption(f"Enabled: {selected_definition.is_enabled}")

    generated_command = _build_crawl_command(
        selected_source_name,
        identifier_value,
        int(max_jobs_value),
    )

    st.sidebar.markdown("**Suggested Crawl Command**")
    st.sidebar.code(generated_command, language="powershell")

    st.sidebar.markdown("**Suggested Parse Command**")
    st.sidebar.code(
        f".\\.venv\\Scripts\\python.exe -m job_scraper.cli parse --source {selected_source_name}",
        language="powershell",
    )

    st.sidebar.markdown("**Suggested Enrich Command**")
    st.sidebar.code(
        f".\\.venv\\Scripts\\python.exe -m job_scraper.cli enrich --source {selected_source_name} --limit 20",
        language="powershell",
    )

    rows = _load_rows()

    if not rows:
        st.warning("No jobs found yet. Use the control panel commands to crawl, parse, and enrich jobs first.")
        return

    source_options = _unique_text_values([row.get("source") for row in rows])
    company_options = _unique_text_values([row.get("company") for row in rows])
    location_options = _unique_text_values([row.get("location_raw") for row in rows])
    role_family_options = _unique_text_values([row.get("role_family") for row in rows])
    seniority_options = _unique_text_values([row.get("seniority") for row in rows])
    remote_type_options = _unique_text_values([row.get("remote_type") for row in rows])
    skill_options = _all_skills(rows)

    st.sidebar.header("Saved Job Filters")
    selected_sources = st.sidebar.multiselect("Saved Sources", source_options)
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
