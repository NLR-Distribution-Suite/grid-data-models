"""Three-phase distribution system reduction."""

from collections import defaultdict
from typing import Type

from infrasys.time_series_models import SingleTimeSeries, TimeSeriesData
import networkx as nx

from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.systems.distribution.distribution_system import DistributionSystem
from gdm.systems.distribution.enums import Phase
from gdm.systems.distribution.model_reduction.common import _reduce_system

_THREE_PHASE_SET: frozenset[Phase] = frozenset({Phase.A, Phase.B, Phase.C})


def _component_three_phase_boundary(
    component: set[str],
    graph: nx.MultiGraph,
    three_phase_bus_names: set[str],
) -> set[str]:
    return {
        neighbor
        for node in component
        for neighbor in graph.neighbors(node)
        if neighbor in three_phase_bus_names
    }


def _cluster_group_phases(
    dist_system: DistributionSystem,
    clusters: list[set[str]],
) -> set[Phase]:
    phases: set[Phase] = set()
    for cluster in clusters:
        for bus_name in cluster:
            phases.update(dist_system.get_component(DistributionBus, bus_name).phases)
    return phases


def _get_intermediate_phase_split_buses(
    dist_system: DistributionSystem,
    three_phase_bus_names: set[str],
    graph: nx.MultiGraph,
) -> list[str]:
    """Return non-3ph buses that sit between 3ph buses as a phase-split section.

    A non-3ph connected component (cluster) qualifies as an "intermediate" if it
    touches at least two three-phase buses on the graph. Clusters that share the
    same three-phase boundary are grouped together (this captures the common
    pattern where a 3ph segment is temporarily represented as parallel
    single-phase branches, one per phase, each on its own bus). A group is kept
    only if the union of phases across all its clusters covers phases A, B, C.
    """
    non_three_phase_nodes = [n for n in graph.nodes() if n not in three_phase_bus_names]
    non_three_phase_subgraph = graph.subgraph(non_three_phase_nodes)

    groups: dict[frozenset[str], list[set[str]]] = defaultdict(list)
    for component in nx.connected_components(non_three_phase_subgraph):
        boundary = _component_three_phase_boundary(component, graph, three_phase_bus_names)
        if len(boundary) < 2:
            continue
        groups[frozenset(boundary)].append(set(component))

    kept: list[str] = []
    for clusters in groups.values():
        if not _THREE_PHASE_SET.issubset(_cluster_group_phases(dist_system, clusters)):
            continue
        for cluster in clusters:
            kept.extend(cluster)
    return kept


def _get_three_phase_buses(
    dist_system: DistributionSystem,
    include_intermediate_buses: bool = False,
) -> list[str]:
    three_phase_buses = [
        bus.name
        for bus in dist_system.get_components(
            DistributionBus,
            filter_func=lambda x: set((Phase.A, Phase.B, Phase.C)).issubset(x.phases),
        )
    ]
    graph = dist_system.get_undirected_graph()

    candidate_buses: set[str] = set(three_phase_buses)
    if include_intermediate_buses:
        candidate_buses.update(
            _get_intermediate_phase_split_buses(dist_system, set(three_phase_buses), graph)
        )

    subgraph = graph.subgraph(candidate_buses)
    connected_components = list(nx.connected_components(subgraph))

    max_size = 0
    max_size_set: set[str] | list[str] = list(candidate_buses)
    for island in connected_components:
        if len(island) > max_size:
            max_size = len(island)
            max_size_set = island

    return list(max_size_set)


def reduce_to_three_phase_system(
    dist_system: DistributionSystem,
    name: str,
    agg_time_series: bool = False,
    agg_timeseries: bool | None = None,
    time_series_type: Type[TimeSeriesData] = SingleTimeSeries,
    include_intermediate_buses: bool = False,
) -> DistributionSystem:
    three_phase_buses = _get_three_phase_buses(
        dist_system, include_intermediate_buses=include_intermediate_buses
    )
    return _reduce_system(
        dist_system,
        three_phase_buses,
        name,
        agg_time_series,
        agg_timeseries,
        time_series_type,
        allow_cycles=include_intermediate_buses,
    )
