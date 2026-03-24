from dataclasses import dataclass


# Store the metadata the app needs to describe and select a source.
@dataclass(frozen=True)
class SourceDefinition:
    name: str
    display_name: str
    transport_type: str
    identifier_label: str
    identifier_placeholder: str
    is_enabled: bool


# Define every source the UI and CLI should know about.
SOURCE_DEFINITIONS: dict[str, SourceDefinition] = {
    "greenhouse": SourceDefinition(
        name="greenhouse",
        display_name="Greenhouse",
        transport_type="html",
        identifier_label="Board token",
        identifier_placeholder="greenhouse",
        is_enabled=True,
    ),
    "weworkremotely": SourceDefinition(
        name="weworkremotely",
        display_name="We Work Remotely",
        transport_type="html",
        identifier_label="Site",
        identifier_placeholder="weworkremotely",
        is_enabled=False,
    ),
    "lever": SourceDefinition(
        name="lever",
        display_name="Lever",
        transport_type="api",
        identifier_label="Site",
        identifier_placeholder="welocalize",
        is_enabled=True
    ),
    "ashby": SourceDefinition(
        name="ashby",
        display_name="Ashby",
        transport_type="api",
        identifier_label="Job board name",
        identifier_placeholder="ashby",
        is_enabled=True,
    ),
    "workable": SourceDefinition(
        name="workable",
        display_name="Workable",
        transport_type="api",
        identifier_label="Subdomain",
        identifier_placeholder="company-subdomain",
        is_enabled=False,
    ),
}


# Return one source definition by name and fail clearly if it does not exist.
def get_source_definition(source_name: str) -> SourceDefinition:
    try:
        return SOURCE_DEFINITIONS[source_name]
    except KeyError as error:
        raise ValueError(f"Unsupported source: {source_name}") from error


# Return all source definitions in one list for UI and CLI use.
def list_source_definitions() -> list[SourceDefinition]:
    return list(SOURCE_DEFINITIONS.values())


# Return only source definitions that are currently enabled for live use.
def list_enabled_source_definitions() -> list[SourceDefinition]:
    return [definition for definition in SOURCE_DEFINITIONS.values() if definition.is_enabled]


# Return only the enabled source names for validation and menus.
def list_enabled_source_names() -> list[str]:
    return [definition.name for definition in list_enabled_source_definitions()]
