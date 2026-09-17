import uuid
from collections import defaultdict
from typing import Type, Union, Callable

from infrasys.time_series_models import SingleTimeSeries, TimeSeriesData
import networkx as nx
import numpy as np

from gdm.distribution.components.distribution_bus import DistributionBus
from gdm.distribution.components.distribution_load import DistributionLoad
from gdm.distribution.components.distribution_solar import DistributionSolar
from gdm.distribution.components.distribution_battery import DistributionBattery
from gdm.distribution.components.matrix_impedance_branch import MatrixImpedanceBranch
from gdm.distribution.distribution_system import (
    DistributionSystem,
    UserAttributes,
)

from gdm.distribution.components.base.distribution_branch_base import DistributionBranchBase
from gdm.distribution.components.base.distribution_transformer_base import (
    DistributionTransformerBase,
)

from gdm.distribution.enums import Phase
from gdm.distribution.sys_functools import (
    get_aggregated_load_time_series,
    get_aggregated_solar_time_series,
    get_aggregated_battery_time_series,
)
from gdm.quantities import Distance


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


def _get_primary_buses(dist_system: DistributionSystem) -> list[str]:
    return [
        bus.name
        for bus in dist_system.get_components(
            DistributionBus,
            filter_func=lambda x: x.rated_voltage.to("kilovolt").magnitude > 1.0,
        )
    ]


def _get_aggregated_bus_component(
    subtree_system: DistributionSystem,
    bus: DistributionBus,
    model_type: DistributionLoad | DistributionSolar,
    split_phase_mapping: dict[str, set[Phase]],
) -> DistributionLoad | DistributionSolar:
    model_components = subtree_system.get_components(model_type)
    return model_type.aggregate(
        instances=list(model_components),
        bus=bus,
        name=str(uuid.uuid4()),
        split_phase_mapping=split_phase_mapping,
    )


def _reduce_system(
    dist_system: DistributionSystem,
    bus_subset: list[DistributionBus],
    name: str,
    agg_time_series: bool = False,
    agg_timeseries: bool | None = None,
    time_series_type: Type[TimeSeriesData] = SingleTimeSeries,
) -> DistributionSystem:
    if agg_timeseries is not None:
        agg_time_series = agg_timeseries

    original_tree = dist_system.get_directed_graph()
    reduced_system = dist_system.get_subsystem(
        bus_subset,
        name,
        keep_time_series=agg_time_series,
        time_series_type=time_series_type,
        directed_graph=original_tree,
    )

    split_phase_mapping = dist_system.get_split_phase_mapping(directed_graph=original_tree)
    reduced_network_tree = original_tree.subgraph(bus_subset)
    ts_agg_func_mapper: dict[Union[Type[DistributionLoad], Type[DistributionSolar]], Callable] = {
        DistributionLoad: get_aggregated_load_time_series,
        DistributionSolar: get_aggregated_solar_time_series,
        DistributionBattery: get_aggregated_battery_time_series,
    }
    for node in reduced_network_tree.nodes():
        if reduced_network_tree.out_degree(node) < original_tree.out_degree(node):
            sucessors_diff = set(original_tree.successors(node)) - set(
                reduced_network_tree.successors(node)
            )
            successors_descendants = [
                snode
                for successor in sucessors_diff
                for snode in nx.descendants(original_tree, successor)
            ] + list(sucessors_diff)
            subtree = original_tree.subgraph(successors_descendants)
            subtree_system = dist_system.get_subsystem(
                list(subtree.nodes),
                "",
                directed_graph=original_tree,
            )
            model_types = subtree_system.get_model_types_with_field_type(DistributionBus)
            for model_type in model_types:
                agg_component = _get_aggregated_bus_component(
                    subtree_system,
                    reduced_system.get_component(DistributionBus, node),
                    model_type=model_type,
                    split_phase_mapping=split_phase_mapping,
                )
                reduced_system.add_component(agg_component)
                agg_comp = reduced_system.get_component(model_type, agg_component.name)
                if agg_time_series:
                    comps = list(subtree_system.get_components(model_type))
                    ts_metadata = dist_system.list_time_series_metadata(
                        comps[0], time_series_type=time_series_type
                    )
                    for metadata in ts_metadata:
                        ts_aggregate = ts_agg_func_mapper[model_type](
                            dist_system,
                            comps,
                            metadata.name,
                            time_series_type,
                            **metadata.features,
                        )
                        user_attr = UserAttributes.model_validate(metadata.features)
                        user_attr.use_actual = True
                        reduced_system.add_time_series(
                            ts_aggregate,
                            agg_comp,
                            **user_attr.model_dump(),
                            **{
                                k: v
                                for k, v in metadata.features.items()
                                if k not in user_attr.model_dump()
                            },
                        )
    return reduced_system


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
    )


def reduce_to_primary_system(
    dist_system: DistributionSystem,
    name: str,
    agg_time_series: bool = False,
    agg_timeseries: bool | None = None,
    time_series_type: Type[TimeSeriesData] = SingleTimeSeries,
) -> DistributionSystem:
    primary_buses = _get_primary_buses(dist_system)
    return _reduce_system(
        dist_system,
        primary_buses,
        name,
        agg_time_series,
        agg_timeseries,
        time_series_type,
    )



















































































def _branches_are_compatible(
    branch_a: MatrixImpedanceBranch,
    branch_b: MatrixImpedanceBranch,
) -> bool:
    """Check if two MatrixImpedanceBranch components can be merged.

    Branches are compatible if they have identical phases, construction type,
    ampacity, and per-unit-length impedance/capacitance matrices.
    """
    if sorted(branch_a.phases, key=lambda p: p.value) != sorted(
        branch_b.phases, key=lambda p: p.value
    ):
        return False

    eq_a = branch_a.equipment
    eq_b = branch_b.equipment

    if eq_a.construction != eq_b.construction:
        return False

    if not np.isclose(
        eq_a.ampacity.to("ampere").magnitude,
        eq_b.ampacity.to("ampere").magnitude,
        rtol=1e-6,
    ):
        return False

    for mat_attr in ("r_matrix", "x_matrix", "c_matrix"):
        mat_a = getattr(eq_a, mat_attr)
        mat_b = getattr(eq_b, mat_attr).to(mat_a.units)
        if not np.allclose(mat_a.magnitude, mat_b.magnitude, rtol=1e-6, atol=0):
            return False

    return True


def _merge_branches(
    dist_system: DistributionSystem,
    branch_a: MatrixImpedanceBranch,
    branch_b: MatrixImpedanceBranch,
    middle_bus: DistributionBus,
) -> MatrixImpedanceBranch:
    """Create a merged branch replacing two series branches through a trivial bus."""
    outer_bus_a = (
        branch_a.buses[0] if branch_a.buses[1].name == middle_bus.name else branch_a.buses[1]
    )
    outer_bus_b = (
        branch_b.buses[0] if branch_b.buses[1].name == middle_bus.name else branch_b.buses[1]
    )

    new_length = branch_a.length.to("meter").magnitude + branch_b.length.to("meter").magnitude

    return MatrixImpedanceBranch(
        buses=[outer_bus_a, outer_bus_b],
        length=Distance(new_length, "meter"),
        phases=list(branch_a.phases),
        equipment=branch_a.equipment,
        name=f"{branch_a.name}__{branch_b.name}",
        in_service=branch_a.in_service and branch_b.in_service,
        substation=branch_a.substation,
        feeder=branch_a.feeder,
    )


def _find_buses_with_non_branch_components(dist_system: DistributionSystem) -> set[str]:
    buses_with_components: set[str] = set()
    branch_types = (DistributionBranchBase, DistributionTransformerBase)
    for model_type in dist_system.get_model_types_with_field_type(DistributionBus):
        if issubclass(model_type, branch_types):
            continue
        for comp in dist_system.get_components(model_type):
            bus_field = getattr(comp, "bus", None)
            if bus_field is not None:
                buses_with_components.add(bus_field.name)
    return buses_with_components


def _build_bus_to_branches_map(
    dist_system: DistributionSystem,
) -> dict[str, list[MatrixImpedanceBranch]]:
    bus_to_branches: dict[str, list[MatrixImpedanceBranch]] = {}
    for branch in dist_system.get_components(MatrixImpedanceBranch):
        for bus in branch.buses:
            bus_to_branches.setdefault(bus.name, []).append(branch)
    return bus_to_branches


def _find_trivial_buses(
    dist_system: DistributionSystem,
    graph: nx.MultiGraph,
    buses_with_components: set[str],
    bus_to_branches: dict[str, list[MatrixImpedanceBranch]],
) -> set[str]:
    trivial_buses: set[str] = set()
    source_bus_name = dist_system.get_source_bus().name
    for bus in dist_system.get_components(DistributionBus):
        if bus.name == source_bus_name or bus.name in buses_with_components:
            continue
        if graph.degree(bus.name) != 2:
            continue
        branches = bus_to_branches.get(bus.name, [])
        if len(branches) != 2:
            continue
        if _branches_are_compatible(branches[0], branches[1]):
            trivial_buses.add(bus.name)
    return trivial_buses


def _extend_merge_chain(
    dist_system: DistributionSystem,
    merged: MatrixImpedanceBranch,
    trivial_buses: set[str],
    bus_to_branches: dict[str, list[MatrixImpedanceBranch]],
    consumed_branches: set[str],
    consumed_buses: set[str],
) -> MatrixImpedanceBranch:
    while True:
        extended = False
        for ob in (merged.buses[0].name, merged.buses[1].name):
            if ob not in trivial_buses or ob in consumed_buses:
                continue
            next_branch = next(
                (nb for nb in bus_to_branches[ob] if nb.name not in consumed_branches),
                None,
            )
            if next_branch is None or not _branches_are_compatible(merged, next_branch):
                continue
            ob_bus = dist_system.get_component(DistributionBus, ob)
            merged = _merge_branches(dist_system, merged, next_branch, ob_bus)
            consumed_branches.add(next_branch.name)
            consumed_buses.add(ob)
            extended = True
        if not extended:
            return merged


def reduce_trivial_nodes(
    dist_system: DistributionSystem,
    name: str | None = None,
) -> DistributionSystem:
    """Remove trivial pass-through nodes from the distribution system.

    A bus is trivial if it connects exactly two MatrixImpedanceBranch components
    with identical per-unit-length electrical characteristics (impedance matrices,
    construction type, ampacity) and has no other components attached. The two
    branches are merged into a single branch whose length is the sum of the
    originals.

    Parameters
    ----------
    dist_system : DistributionSystem
        The system to reduce.
    name : str | None
        Name for the reduced system. Defaults to the original name.

    Returns
    -------
    DistributionSystem
        A new reduced system with trivial nodes removed.
    """

    dist_system = dist_system.deepcopy()

    if name is None:
        name = dist_system.name

    graph = dist_system.get_undirected_graph()

    buses_with_components = _find_buses_with_non_branch_components(dist_system)
    bus_to_branches = _build_bus_to_branches_map(dist_system)
    trivial_buses = _find_trivial_buses(dist_system, graph, buses_with_components, bus_to_branches)

    if not trivial_buses:
        return dist_system

    merged_branches: list[MatrixImpedanceBranch] = []
    consumed_branches: set[str] = set()
    consumed_buses: set[str] = set()

    for bus_name in list(trivial_buses):
        if bus_name in consumed_buses:
            continue
        branch_a, branch_b = bus_to_branches[bus_name]
        if branch_a.name in consumed_branches or branch_b.name in consumed_branches:
            continue

        bus = dist_system.get_component(DistributionBus, bus_name)
        merged = _merge_branches(dist_system, branch_a, branch_b, bus)
        consumed_branches.add(branch_a.name)
        consumed_branches.add(branch_b.name)
        consumed_buses.add(bus_name)

        merged = _extend_merge_chain(
            dist_system,
            merged,
            trivial_buses,
            bus_to_branches,
            consumed_branches,
            consumed_buses,
        )
        merged_branches.append(merged)

    for comp_type in [MatrixImpedanceBranch, DistributionBus]:
        for comp in dist_system.get_components(comp_type):
            if comp.name in consumed_buses or comp.name in consumed_branches:
                dist_system.remove_component(comp)

    dist_system.auto_add_composed_components = True
    for merged in merged_branches:
        dist_system.add_component(merged)

    return dist_system
