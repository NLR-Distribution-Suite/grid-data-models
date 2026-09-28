"""Time series utilities for distribution systems."""

from collections import defaultdict
from typing import Optional
from uuid import UUID

from gdm.systems.distribution import DistributionSystem

from gdm.mcp.schemas import TimeSeriesInfo


def get_time_series_summary(system: DistributionSystem) -> dict[str, any]:
    """
    Get a summary of all time series data in the system.

    Args:
        system: DistributionSystem to analyze

    Returns:
        Dictionary with time series statistics:
            - total_components_with_ts: int
            - total_timeseries: int
            - by_component_type: dict mapping type to count
            - by_variable: dict mapping variable name to count
    """
    components_with_ts = 0
    total_timeseries = 0
    by_component_type: dict[str, int] = defaultdict(int)
    by_variable: dict[str, int] = defaultdict(int)

    for component in system.iter_all_components():
        if system.has_time_series(component):
            components_with_ts += 1
            component_type = component.__class__.__name__

            for ts_metadata in system.list_time_series_metadata(component):
                total_timeseries += 1
                by_component_type[component_type] += 1
                by_variable[ts_metadata.name] += 1

    return {
        "total_components_with_ts": components_with_ts,
        "total_timeseries": total_timeseries,
        "by_component_type": dict(by_component_type),
        "by_variable": dict(by_variable),
    }


def list_components_with_timeseries(
    system: DistributionSystem,
    ts_type: Optional[str] = None,
    variable_name: Optional[str] = None,
) -> list[TimeSeriesInfo]:
    """
    List all components with time series data, optionally filtered.

    Args:
        system: DistributionSystem to search
        ts_type: Optional filter by time series type name (e.g., "SingleTimeSeries")
        variable_name: Optional filter by variable name (e.g., "active_power")

    Returns:
        List of TimeSeriesInfo for matching components
    """
    results = []

    for component in system.iter_all_components():
        if not system.has_time_series(component):
            continue

        component_uuid = (
            component.uuid if isinstance(component.uuid, UUID) else UUID(component.uuid)
        )
        component_type = component.__class__.__name__
        component_name = component.name

        for ts_metadata in system.list_time_series_metadata(component):
            ts_type_name = ts_metadata.__class__.__name__
            var_name = ts_metadata.name

            # Apply filters
            if ts_type and ts_type_name != ts_type:
                continue
            if variable_name and var_name != variable_name:
                continue

            # Try to get additional info about the time series
            try:
                ts_data = system.get_time_series(component, var_name, type(ts_metadata))
                length = len(ts_data.data) if hasattr(ts_data, "data") else None
                start_time = None
                end_time = None

                # Try to get time bounds if available
                if hasattr(ts_data, "data") and hasattr(ts_data.data, "index"):
                    index = ts_data.data.index
                    if len(index) > 0:
                        start_time = str(index[0])
                        end_time = str(index[-1])

            except Exception:
                length = None
                start_time = None
                end_time = None

            results.append(
                TimeSeriesInfo(
                    component_uuid=component_uuid,
                    component_name=component_name,
                    component_type=component_type,
                    timeseries_type=ts_type_name,
                    variable_name=var_name,
                    length=length,
                    start_time=start_time,
                    end_time=end_time,
                )
            )

    return results
