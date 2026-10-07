"""Subsystem extraction utilities."""

from gdm.systems.distribution import DistributionSystem
from gdm.systems.distribution.components import DistributionBus
from infrasys import SingleTimeSeries


def export_subsystem_by_buses(
    system: DistributionSystem,
    bus_names: list[str],
    name: str,
    keep_timeseries: bool = True,
) -> DistributionSystem:
    """
    Extract a subsystem containing specified buses and their connected components.

    This uses the GDM's built-in get_subsystem method to ensure proper
    component relationships and connectivity.

    Args:
        system: Source DistributionSystem
        bus_names: List of bus names to include in subsystem
        name: Name for the new subsystem
        keep_timeseries: Whether to preserve time series data

    Returns:
        New DistributionSystem containing only the specified buses and connected components

    Raises:
        ValueError: If bus names are invalid or subsystem cannot be created
    """
    if not bus_names:
        raise ValueError("Must specify at least one bus name")

    # Validate that all bus names exist
    all_buses = system.get_components(DistributionBus)
    available_bus_names = {bus.name for bus in all_buses}
    invalid_buses = set(bus_names) - available_bus_names

    if invalid_buses:
        raise ValueError(
            f"Buses not found in system: {invalid_buses}. "
            f"Available buses: {sorted(available_bus_names)}"
        )

    # Use GDM's get_subsystem method
    time_series_type = SingleTimeSeries if keep_timeseries else None

    subsystem = system.get_subsystem(
        bus_names=bus_names,
        name=name,
        keep_timeseries=keep_timeseries,
        time_series_type=time_series_type,
    )

    return subsystem
