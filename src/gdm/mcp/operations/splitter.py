"""System splitter for disaggregating distribution systems by substation or feeder."""

from collections import defaultdict
from typing import Optional

from gdm.systems.distribution import DistributionSystem
from gdm.systems.distribution.components import DistributionBus

from gdm.mcp.schemas import SplitReport


def split_by_substation(
    system: DistributionSystem,
    keep_timeseries: bool = True,
    include_unassigned: bool = True,
) -> tuple[dict[str, DistributionSystem], SplitReport]:
    """
    Split a distribution system into subsystems by substation.

    Args:
        system: DistributionSystem to split
        keep_timeseries: Whether to preserve time series data
        include_unassigned: Whether to create a system for unassigned components

    Returns:
        Tuple of (subsystems_dict, SplitReport) where subsystems_dict maps substation name to system
    """
    return _split_by_field(
        system=system,
        field_name="substation",
        split_by="substation",
        keep_timeseries=keep_timeseries,
        include_unassigned=include_unassigned,
    )


def split_by_feeder(
    system: DistributionSystem,
    keep_timeseries: bool = True,
    include_unassigned: bool = True,
) -> tuple[dict[str, DistributionSystem], SplitReport]:
    """
    Split a distribution system into subsystems by feeder.

    Args:
        system: DistributionSystem to split
        keep_timeseries: Whether to preserve time series data
        include_unassigned: Whether to create a system for unassigned components

    Returns:
        Tuple of (subsystems_dict, SplitReport) where subsystems_dict maps feeder name to system
    """
    return _split_by_field(
        system=system,
        field_name="feeder",
        split_by="feeder",
        keep_timeseries=keep_timeseries,
        include_unassigned=include_unassigned,
    )


def _group_components(
    system: DistributionSystem,
    field_name: str,
) -> tuple[dict[Optional[str], list], dict[Optional[str], list]]:
    """Group components and buses by field value."""
    component_groups: dict[Optional[str], list] = defaultdict(list)
    bus_groups: dict[Optional[str], list] = defaultdict(list)

    for component in system.iter_all_components():
        field_value = getattr(component, field_name, None)
        if field_value is not None and hasattr(field_value, "name"):
            field_value = field_value.name

        if isinstance(component, DistributionBus):
            bus_groups[field_value].append(component)

        component_groups[field_value].append(component)

    return component_groups, bus_groups


def _create_subsystem(
    system: DistributionSystem,
    subsystem_name: str,
    components: list,
    keep_timeseries: bool,
    warnings: list[str],
) -> DistributionSystem:
    """Create a subsystem from a list of components."""
    subsystem = DistributionSystem(name=subsystem_name)

    for component in components:
        subsystem.add_component(component)

        if keep_timeseries and system.has_time_series(component):
            try:
                for ts_metadata in system.list_time_series_metadata(component):
                    ts_type = type(ts_metadata)
                    ts_data = system.get_time_series(component, ts_metadata.variable_name, ts_type)
                    subsystem.add_time_series(ts_data, component, **ts_metadata.features)
            except Exception as e:
                warnings.append(f"Failed to transfer time series for {component.name}: {str(e)}")

    return subsystem


def _split_by_field(
    system: DistributionSystem,
    field_name: str,
    split_by: str,
    keep_timeseries: bool,
    include_unassigned: bool,
) -> tuple[dict[str, DistributionSystem], SplitReport]:
    """
    Internal method to split system by a field (substation or feeder).

    Args:
        system: DistributionSystem to split
        field_name: Field to split on ("substation" or "feeder")
        split_by: Description for report ("substation" or "feeder")
        keep_timeseries: Whether to preserve time series data
        include_unassigned: Whether to create a system for unassigned components

    Returns:
        Tuple of (subsystems_dict, SplitReport)
    """
    warnings: list[str] = []
    component_groups, bus_groups = _group_components(system, field_name)

    # Remove None group if not including unassigned
    unassigned_count = len(component_groups.get(None, []))
    if not include_unassigned and None in component_groups:
        warnings.append(
            f"Excluded {unassigned_count} unassigned components (no {field_name} specified)"
        )
        del component_groups[None]

    # Create subsystems
    subsystems: dict[str, DistributionSystem] = {}
    subsystem_counts: dict[str, int] = {}

    for field_value, components in component_groups.items():
        subsystem_name = (
            f"{system.name}_unassigned" if field_value is None else f"{system.name}_{field_value}"
        )

        try:
            subsystem = _create_subsystem(
                system, subsystem_name, components, keep_timeseries, warnings
            )

            bus_count = len([c for c in components if isinstance(c, DistributionBus)])
            if bus_count == 0:
                warnings.append(f"Subsystem '{subsystem_name}' has no buses - may be invalid")

            key = field_value if field_value is not None else "unassigned"
            subsystems[key] = subsystem
            subsystem_counts[key] = len(components)

        except Exception as e:
            warnings.append(f"Failed to create subsystem for {field_value}: {str(e)}")

    # Check if split was successful
    if not subsystems:
        return {}, SplitReport(
            success=False,
            input_system_name=system.name,
            output_count=0,
            split_by=split_by,
            error_message=f"No subsystems created. System may not have {field_name} assignments.",
        )

    return subsystems, SplitReport(
        success=True,
        input_system_name=system.name,
        output_count=len(subsystems),
        split_by=split_by,
        subsystems=subsystem_counts,
        unassigned_components=unassigned_count if not include_unassigned else 0,
        timeseries_preserved=keep_timeseries,
        warnings=warnings,
    )
