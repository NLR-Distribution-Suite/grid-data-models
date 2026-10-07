"""Inspector for querying and summarizing distribution systems."""

import contextlib
from collections import defaultdict
from uuid import UUID

from gdm.systems.distribution import DistributionSystem

from gdm.mcp.exceptions import ComponentNotFoundError
from gdm.mcp.schemas import (
    ComponentFilter,
    ComponentInfo,
    ComponentSummary,
    FeederSummary,
    SubstationSummary,
    SystemSummary,
)


def get_system_summary(system: DistributionSystem) -> SystemSummary:
    """
    Get a comprehensive summary of a distribution system.

    Args:
        system: DistributionSystem to summarize

    Returns:
        SystemSummary with component counts, substations, feeders, and time series info
    """
    components_by_type: dict[str, dict] = defaultdict(lambda: {"count": 0, "with_timeseries": 0})
    substation_data: dict[str, dict] = defaultdict(
        lambda: {"feeders": set(), "components": 0, "buses": 0}
    )
    feeder_data: dict[str, dict] = defaultdict(
        lambda: {"substation": None, "components": 0, "buses": 0}
    )

    total_components = 0
    total_timeseries = 0
    has_any_timeseries = False

    for component in system.iter_all_components():
        total_components += 1
        component_type = component.__class__.__name__
        components_by_type[component_type]["count"] += 1

        # Check for time series
        if system.has_time_series(component):
            components_by_type[component_type]["with_timeseries"] += 1
            has_any_timeseries = True
            ts_count = len(list(system.list_time_series_metadata(component)))
            total_timeseries += ts_count

        # Track substation and feeder
        substation = getattr(component, "substation", None)
        feeder = getattr(component, "feeder", None)

        if substation is not None:
            sub_name = substation.name if hasattr(substation, "name") else str(substation)
            substation_data[sub_name]["components"] += 1
            if component_type == "DistributionBus":
                substation_data[sub_name]["buses"] += 1

            if feeder is not None:
                feeder_name = feeder.name if hasattr(feeder, "name") else str(feeder)
                substation_data[sub_name]["feeders"].add(feeder_name)

        if feeder is not None:
            feeder_name = feeder.name if hasattr(feeder, "name") else str(feeder)
            feeder_data[feeder_name]["components"] += 1
            if component_type == "DistributionBus":
                feeder_data[feeder_name]["buses"] += 1
            if substation is not None:
                sub_name = substation.name if hasattr(substation, "name") else str(substation)
                feeder_data[feeder_name]["substation"] = sub_name

    # Build component summaries
    component_summaries = [
        ComponentSummary(
            component_type=comp_type,
            count=data["count"],
            with_timeseries=data["with_timeseries"],
        )
        for comp_type, data in sorted(components_by_type.items())
    ]

    # Build substation summaries
    substation_summaries = [
        SubstationSummary(
            name=name,
            feeder_count=len(data["feeders"]),
            component_count=data["components"],
            bus_count=data["buses"],
        )
        for name, data in sorted(substation_data.items())
    ]

    # Build feeder summaries
    feeder_summaries = [
        FeederSummary(
            name=name,
            substation=data["substation"],
            component_count=data["components"],
            bus_count=data["buses"],
        )
        for name, data in sorted(feeder_data.items())
    ]

    return SystemSummary(
        name=system.name,
        total_components=total_components,
        components_by_type=component_summaries,
        substations=substation_summaries,
        feeders=feeder_summaries,
        has_timeseries=has_any_timeseries,
        timeseries_count=total_timeseries,
    )


def _get_field_name(obj) -> str | None:
    """Extract a name string from a field that may be an object or string."""
    if obj is None:
        return None
    return obj.name if hasattr(obj, "name") else str(obj)


def _matches_substation(component, expected: str | None) -> bool:
    """Check if component matches the substation filter."""
    if expected is None:
        return True
    substation = getattr(component, "substation", None)
    return substation is not None and _get_field_name(substation) == expected


def _matches_feeder(component, expected: str | None) -> bool:
    """Check if component matches the feeder filter."""
    if expected is None:
        return True
    feeder = getattr(component, "feeder", None)
    return feeder is not None and _get_field_name(feeder) == expected


def _matches_phases(component, expected_phases) -> bool:
    """Check if component matches the phases filter."""
    if expected_phases is None:
        return True
    phases = getattr(component, "phases", None)
    return phases is not None and set(phases) == set(expected_phases)


def _matches_filters(component, filters: ComponentFilter, system: DistributionSystem) -> bool:
    """Check if a component matches all filter criteria."""
    if filters.component_types and component.__class__.__name__ not in filters.component_types:
        return False

    if not _matches_substation(component, filters.substation):
        return False

    if not _matches_feeder(component, filters.feeder):
        return False

    if not _matches_phases(component, filters.phases):
        return False

    if filters.in_service is not None:
        if getattr(component, "in_service", None) != filters.in_service:
            return False

    if filters.has_timeseries is not None:
        if system.has_time_series(component) != filters.has_timeseries:
            return False

    return True


def _build_component_info(component) -> ComponentInfo:
    """Build a ComponentInfo from a component."""
    substation = getattr(component, "substation", None)
    feeder = getattr(component, "feeder", None)
    phases = getattr(component, "phases", None)
    in_service = getattr(component, "in_service", None)

    return ComponentInfo(
        uuid=component.uuid if isinstance(component.uuid, UUID) else UUID(component.uuid),
        component_type=component.__class__.__name__,
        name=component.name,
        substation=substation.name if substation and hasattr(substation, "name") else None,
        feeder=feeder.name if feeder and hasattr(feeder, "name") else None,
        phases=phases,
        in_service=in_service,
    )


def query_components(
    system: DistributionSystem,
    filters: ComponentFilter,
) -> list[ComponentInfo]:
    """
    Query components with filters.

    Args:
        system: DistributionSystem to query
        filters: ComponentFilter with query criteria

    Returns:
        List of ComponentInfo for matching components
    """
    return [
        _build_component_info(component)
        for component in system.iter_all_components()
        if _matches_filters(component, filters, system)
    ]


def get_component_details(
    system: DistributionSystem,
    identifier: str,
) -> dict:
    """
    Get detailed information about a component.

    Args:
        system: DistributionSystem to search
        identifier: UUID or name of component

    Returns:
        Dictionary with full component data

    Raises:
        ComponentNotFoundError: If component not found
    """
    component = None

    # Try as UUID first
    with contextlib.suppress(Exception):
        component = system.get_component_by_uuid(identifier)

    # Try as name if UUID lookup failed
    if component is None:
        # Search through all components
        for comp in system.iter_all_components():
            if comp.name == identifier:
                component = comp
                break

    if component is None:
        raise ComponentNotFoundError(f"Component not found: {identifier}")

    # Convert to dict (using Pydantic model_dump if available)
    if hasattr(component, "model_dump"):
        return component.model_dump()
    elif hasattr(component, "dict"):
        return component.dict()
    else:
        # Fallback to basic dict conversion
        return {
            "uuid": component.uuid,
            "name": component.name,
            "type": component.__class__.__name__,
        }
