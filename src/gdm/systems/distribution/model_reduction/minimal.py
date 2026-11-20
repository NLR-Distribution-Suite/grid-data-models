from collections import defaultdict, deque
from infrasys import Component

from gdm.hashing_utils import remove_unreferenced_equipment
from gdm.systems.distribution import DistributionSystem
from gdm.systems.distribution.model_reduction.common import (
    _aggregate_subtree_components,
    _closed_edge_graph,
    _reduce_system,
    _time_series_aggregators,
)
from gdm.systems.distribution.model_reduction.primary import _get_primary_buses
from gdm.systems.distribution.model_reduction.series import _find_chains, _merge_chain

from gdm.systems.distribution.components.base.distribution_switch_base import (
    DistributionSwitchBase,
)
from gdm.systems.distribution.components.base.distribution_component_base import (
    InServiceDistributionComponentBase,
)
from gdm.systems.distribution.components import DistributionBus
from gdm.systems.distribution.components.matrix_impedance_branch import MatrixImpedanceBranch
from gdm.systems.distribution.components.geometry_branch import GeometryBranch


from infrasys.time_series_models import SingleTimeSeries, TimeSeriesData
import networkx as nx


def _nearest_retained_buses(
    graph: nx.Graph, retained: set[str]
) -> tuple[dict[str, str], dict[str, str]]:
    targets = {node: node for node in retained}
    parents: dict[str, str] = {}
    queue = deque(sorted(retained))
    while queue:
        node = queue.popleft()
        for neighbor in sorted(graph.neighbors(node)):
            if neighbor not in targets:
                targets[neighbor] = targets[node]
                parents[neighbor] = node
                queue.append(neighbor)
    return targets, parents


def _out_of_service_buses(system: DistributionSystem) -> set[str]:
    protected = set()
    for component in system.get_components(InServiceDistributionComponentBase):
        if component.in_service:
            continue
        if isinstance(component, DistributionBus):
            protected.add(component.name)
        elif hasattr(component, "buses"):
            protected.update(bus.name for bus in component.buses)
        elif hasattr(component, "bus") and isinstance(component.bus, DistributionBus):
            protected.add(component.bus.name)
        else:
            raise ValueError(
                f"Cannot retain out-of-service {type(component).__name__}.{component.name}"
            )
    return protected


def _retain_protected_paths(graph: nx.Graph, retained: set[str], protected: set[str]) -> set[str]:
    retained = retained.copy()
    for island in nx.connected_components(graph):
        if not island & retained:
            retained.add(min(island & protected or island))
    _, parents = _nearest_retained_buses(graph, retained)
    for node in protected:
        retained.add(node)
        while node in parents:
            node = parents[node]
            retained.add(node)
    return retained


def _closed_forest(graph: nx.Graph, source: str, primary_buses: set[str]) -> nx.DiGraph:
    forest = nx.DiGraph()
    for island in nx.connected_components(graph):
        root = source if source in island else min(island & primary_buses or island)
        forest.add_edges_from(nx.bfs_edges(graph, root, sort_neighbors=sorted))
        forest.add_nodes_from(island)
    return forest


def _switch_path_buses(graph: nx.MultiGraph, switch_buses: set[str]) -> set[str]:
    retained = switch_buses.copy()
    for bus_i in switch_buses:
        for bus_j in switch_buses:
            if not nx.has_path(graph, bus_i, bus_j):
                continue
            shortest_path = nx.shortest_path(graph, source=bus_i, target=bus_j)
            edge_nodes = list(zip(shortest_path[:-1], shortest_path[1:]))
            if all(
                any(not data["is_switch"] for data in graph[u][v].values()) for u, v in edge_nodes
            ):
                for u, v in edge_nodes:
                    retained.add(u)
                    retained.add(v)
    return retained


def _series_lateral_with_consistant_buses(
    system: DistributionSystem,
    graph: nx.MultiGraph,
    agg_time_series: bool = False,
    time_series_type: type[TimeSeriesData] = SingleTimeSeries,
) -> nx.MultiGraph:
    nodes_with_degree_three_plus = {node for node in graph if graph.degree(node) >= 3}
    lateral_graph = graph.subgraph(set(graph) - nodes_with_degree_three_plus).copy()
    _remove_switches_from_graph(lateral_graph)
    eligible = []
    for island in nx.connected_components(lateral_graph):
        if len(island) <= 2:
            continue
        phases = {frozenset(system.get_component(DistributionBus, bus).phases) for bus in island}
        if len(phases) == 1:
            eligible.append(island)

    source = system.get_source_bus().name
    distances = nx.single_source_shortest_path_length(graph, source)
    for nodes, branches in _find_chains(system, graph, source):
        if not any(set(nodes[1:-1]).issubset(island) for island in eligible):
            continue
        if (
            len({frozenset(system.get_component(DistributionBus, node).phases) for node in nodes})
            != 1
        ):
            continue
        equivalents = [
            branch.to_matrix_representation() if isinstance(branch, GeometryBranch) else branch
            for branch in branches
        ]
        lengths = [branch.length.to("meter").magnitude for branch in equivalents]
        total_length = sum(lengths)
        if total_length <= 0:
            raise ValueError(f"Cannot merge zero-length series branches: {nodes}")
        equipment = equivalents[0].equipment
        if isinstance(equivalents[0], MatrixImpedanceBranch):
            fields = ("r_matrix", "x_matrix", "c_matrix")
        else:
            fields = (
                "pos_seq_resistance",
                "zero_seq_resistance",
                "pos_seq_reactance",
                "zero_seq_reactance",
                "pos_seq_capacitance",
                "zero_seq_capacitance",
            )
        updates = {
            field: sum(
                getattr(branch.equipment, field).to(getattr(equipment, field).units) * length
                for branch, length in zip(equivalents, lengths)
            )
            / total_length
            for field in fields
        }
        _merge_chain(
            system,
            nodes,
            branches,
            distances,
            updates,
            equivalents,
            agg_time_series,
            time_series_type,
        )
    return system.get_undirected_graph()


def _remove_switches_from_graph(graph: nx.MultiGraph) -> nx.Graph:
    edges_to_remove = [
        (u, v, k)
        for u, v, k, data in graph.edges(keys=True, data=True)
        if data.get("is_switch", False)
    ]
    print(f"Number of switches removed: {len(edges_to_remove)}")
    graph.remove_edges_from(edges_to_remove)
    return graph


def _ensure_retained_buses(
    primary_system: DistributionSystem,
    reduced_system: DistributionSystem,
    retained_nodes: list[str],
    agg_time_series: bool,
    time_series_type: type[TimeSeriesData],
) -> None:
    for bus_name in retained_nodes:
        bus = primary_system.get_component(DistributionBus, bus_name)
        if reduced_system.has_component(bus):
            continue
        reduced_system.add_component(bus)
        if agg_time_series:
            for metadata in primary_system.list_time_series_metadata(
                bus, time_series_type=time_series_type
            ):
                ts = primary_system.get_time_series(
                    bus, metadata.name, time_series_type=time_series_type, **metadata.features
                )
                reduced_system.add_time_series(ts, bus, **metadata.features)


def _check_removed_time_series(
    source: DistributionSystem,
    reduced: DistributionSystem,
    time_series_type: type[TimeSeriesData],
    asset_mapping: list[tuple[str, str, str]],
) -> None:
    aggregated = {(type_name, name) for type_name, name, _ in asset_mapping}
    for component in source.get_components(Component):
        if (
            (type(component).__name__, component.name) in aggregated
            or (hasattr(component, "bus") and not getattr(component, "in_service", True))
            or reduced.has_component(component)
            or not source.has_time_series(component, time_series_type=time_series_type)
        ):
            continue
        raise ValueError(
            f"Cannot remove {type(component).__name__}.{component.name} with time series: "
            "aggregation is unsupported."
        )


def _reduce_primary(
    system: DistributionSystem,
    agg_time_series: bool,
    time_series_type: type[TimeSeriesData],
    retain_out_of_service: bool,
) -> tuple[DistributionSystem, set[str]]:
    primary_buses = _get_primary_buses(system)
    protected_buses: set[str] = set()
    forest = None
    if retain_out_of_service:
        protected_buses = _out_of_service_buses(system)
        closed_graph = _closed_edge_graph(system)
        forest = _closed_forest(closed_graph, system.get_source_bus().name, set(primary_buses))
        primary_buses = sorted(
            _retain_protected_paths(closed_graph, set(primary_buses), protected_buses)
        )
    primary_mapping: list[tuple[str, str, str]] = []
    primary_system = _reduce_system(
        system,
        primary_buses,
        "primary_system",
        agg_time_series=agg_time_series,
        time_series_type=time_series_type,
        strict_time_series=agg_time_series,
        asset_mapping=primary_mapping if agg_time_series else None,
        directed_graph=forest,
    )
    if retain_out_of_service:
        _ensure_retained_buses(
            system, primary_system, primary_buses, agg_time_series, time_series_type
        )
    if agg_time_series:
        _check_removed_time_series(system, primary_system, time_series_type, primary_mapping)
    return primary_system, protected_buses


def _check_retained_outages(
    source: DistributionSystem, reduced: DistributionSystem, retain_out_of_service: bool
) -> None:
    if not retain_out_of_service:
        return
    for component in source.get_components(InServiceDistributionComponentBase):
        if not component.in_service and not reduced.has_component(component):
            raise ValueError(
                f"Failed to retain out-of-service {type(component).__name__}.{component.name}"
            )


def reduce_to_minimal_system_with_sw(
    system: DistributionSystem,
    reduce_series_laterals: bool = False,
    agg_time_series: bool = False,
    agg_timeseries: bool | None = None,
    time_series_type: type[TimeSeriesData] = SingleTimeSeries,
    retain_out_of_service: bool = False,
) -> DistributionSystem:
    """Reduce to switch-connected buses, aggregating removed assets at nearest retained buses.

    The source bus and its shortest closed path to the retained network are kept.
    With series reduction enabled, compatible matrix, sequence, and geometry
    branches are merged using length-weighted per-unit values and minimum
    ampacity. Geometry conversion uses 60 Hz and 100 ohm-m soil resistivity.
    Intermediate assets are aggregated towards the source. Protected or
    incompatible chains are retained. When agg_time_series is enabled, the
    selected time-series type is retained and load and solar profiles are
    aggregated. Unsupported or mismatched profiles raise an error when their
    components must be aggregated. agg_timeseries overrides agg_time_series
    when provided. When retain_out_of_service is enabled, out-of-service
    components and the buses and paths needed to retain them remain in the
    system, without being aggregated into in-service components.
    """
    if agg_timeseries is not None:
        agg_time_series = agg_timeseries
    primary_system, protected_buses = _reduce_primary(
        system, agg_time_series, time_series_type, retain_out_of_service
    )
    switches = primary_system.get_components(DistributionSwitchBase)
    switch_buses = {bus.name for sw in switches for bus in sw.buses}
    graph = primary_system.get_undirected_graph()

    shortest_path_buses = _switch_path_buses(graph, switch_buses)
    closed_graph = _closed_edge_graph(primary_system)
    source = primary_system.get_source_bus().name
    _, parents = _nearest_retained_buses(closed_graph, shortest_path_buses)
    node = source
    shortest_path_buses.add(node)
    while node in parents:
        node = parents[node]
        shortest_path_buses.add(node)

    if retain_out_of_service:
        shortest_path_buses = _retain_protected_paths(
            closed_graph, shortest_path_buses, protected_buses
        )
    graph_with_no_branching = graph.subgraph(shortest_path_buses).copy()
    targets, _ = _nearest_retained_buses(closed_graph, shortest_path_buses)
    unreachable = set(graph) - set(targets)
    if unreachable:
        raise ValueError(f"No retained bus reachable from buses: {sorted(unreachable)}")

    retained_nodes = sorted(shortest_path_buses)
    all_nodes = nx.DiGraph()
    all_nodes.add_nodes_from(graph)
    reduced_system = primary_system.get_subsystem(
        retained_nodes,
        "minimal_system",
        keep_time_series=agg_time_series,
        time_series_type=time_series_type,
        directed_graph=all_nodes,
    )
    _ensure_retained_buses(
        primary_system, reduced_system, retained_nodes, agg_time_series, time_series_type
    )

    groups: dict[str, list[str]] = defaultdict(list)
    for bus_name in sorted(set(graph) - shortest_path_buses):
        groups[targets[bus_name]].append(bus_name)
    model_types = primary_system.get_model_types_with_field_type(DistributionBus)
    if retain_out_of_service:
        primary_forest = _closed_forest(
            closed_graph, source, set(_get_primary_buses(primary_system))
        )
        split_phase_mapping = primary_system.get_split_phase_mapping(directed_graph=primary_forest)
    else:
        split_phase_mapping = primary_system.get_split_phase_mapping()
    aggregated_component_uuids = set()
    asset_mapping: list[tuple[str, str, str]] = []
    for target, bus_names in groups.items():
        _aggregate_subtree_components(
            primary_system,
            primary_system,
            reduced_system,
            model_types,
            bus_names,
            aggregated_component_uuids,
            reduced_system.get_component(DistributionBus, target),
            split_phase_mapping,
            agg_time_series,
            time_series_type,
            _time_series_aggregators(),
            strict_time_series=agg_time_series,
            asset_mapping=asset_mapping if agg_time_series else None,
        )

    if agg_time_series:
        _check_removed_time_series(primary_system, reduced_system, time_series_type, asset_mapping)

    if reduce_series_laterals:
        _series_lateral_with_consistant_buses(
            reduced_system, graph_with_no_branching, agg_time_series, time_series_type
        )
    _check_retained_outages(system, reduced_system, retain_out_of_service)
    return remove_unreferenced_equipment(reduced_system)
