"""Primary distribution system reduction."""

from typing import Type

from infrasys.time_series_models import SingleTimeSeries, TimeSeriesData

from gdm.hashing_utils import remove_unreferenced_equipment
from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.systems.distribution.distribution_system import DistributionSystem
from gdm.systems.distribution.model_reduction.common import _reduce_system


def _get_primary_buses(dist_system: DistributionSystem) -> list[str]:
    return [
        bus.name
        for bus in dist_system.get_components(
            DistributionBus,
            filter_func=lambda x: x.rated_voltage.to("kilovolt").magnitude > 1.0,
        )
    ]


def reduce_to_primary_system(
    dist_system: DistributionSystem,
    name: str,
    agg_time_series: bool = False,
    agg_timeseries: bool | None = None,
    time_series_type: Type[TimeSeriesData] = SingleTimeSeries,
) -> DistributionSystem:
    primary_buses = _get_primary_buses(dist_system)
    return remove_unreferenced_equipment(
        _reduce_system(
            dist_system,
            primary_buses,
            name,
            agg_time_series,
            agg_timeseries,
            time_series_type,
        )
    )
