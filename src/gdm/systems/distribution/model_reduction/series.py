"""Helpers for reducing compatible series branches."""

from uuid import uuid4

from infrasys.time_series_models import SingleTimeSeries, TimeSeriesData
from loguru import logger
import networkx as nx

from gdm.quantities import Distance
from gdm.systems.distribution.components.base.distribution_branch_base import (
    DistributionBranchBase,
)
from gdm.systems.distribution.components.distribution_battery import DistributionBattery
from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.systems.distribution.components.distribution_capacitor import DistributionCapacitor
from gdm.systems.distribution.components.distribution_generator import DistributionGenerator
from gdm.systems.distribution.components.distribution_load import DistributionLoad
from gdm.systems.distribution.components.distribution_solar import DistributionSolar
from gdm.systems.distribution.components.geometry_branch import GeometryBranch
from gdm.systems.distribution.components.matrix_impedance_branch import MatrixImpedanceBranch
from gdm.systems.distribution.components.sequence_impedance_branch import SequenceImpedanceBranch
from gdm.systems.distribution.distribution_system import DistributionSystem
from gdm.systems.distribution.enums import Phase
from gdm.systems.distribution.model_reduction.common import (
    _add_aggregated_time_series,
    _time_series_aggregators,
    _validate_aggregation_time_series,
)

_Branch = MatrixImpedanceBranch | SequenceImpedanceBranch | GeometryBranch
_EquivalentBranch = MatrixImpedanceBranch | SequenceImpedanceBranch
_BRANCH_TYPES = (MatrixImpedanceBranch, SequenceImpedanceBranch, GeometryBranch)
_ASSET_TYPES = (
    DistributionLoad,
    DistributionSolar,
    DistributionBattery,
    DistributionCapacitor,
    DistributionGenerator,
)


def _branch_for_edge(system: DistributionSystem, data: dict) -> _Branch | None:
    if data["is_switch"] or not data["in_service"] or data["type"] not in _BRANCH_TYPES:
        return None
    branch = system.get_component(data["type"], data["name"])
    if (
        system.has_time_series(branch)
        or system.has_supplemental_attribute(branch)
        or system.list_parent_components(branch)
    ):
        return None
    return branch


def _bus_can_be_removed(system: DistributionSystem, name: str, source: str) -> bool:
    bus = system.get_component(DistributionBus, name)
    if (
        name == source
        or not bus.in_service
        or system.has_time_series(bus)
        or system.has_supplemental_attribute(bus)
    ):
        return False
    for parent in system.list_parent_components(bus):
        if isinstance(parent, DistributionBranchBase):
            continue
        if type(parent) not in _ASSET_TYPES or not parent.in_service:
            return False
        if system.has_supplemental_attribute(parent) or system.list_parent_components(parent):
            return False
        if system.has_time_series(parent) and type(parent) not in (
            DistributionLoad,
            DistributionSolar,
        ):
            return False
    return True


def _removable_bus(
    system: DistributionSystem, graph: nx.MultiGraph, name: str, source: str
) -> bool:
    if graph.degree(name) != 2 or len(graph[name]) != 2:
        return False
    if not _bus_can_be_removed(system, name, source):
        return False
    first, second = [_branch_for_edge(system, data) for _, _, data in graph.edges(name, data=True)]
    return (
        first is not None
        and second is not None
        and type(first) is type(second)
        and first.phases == second.phases
        and first.feeder == second.feeder
        and first.substation == second.substation
    )


def _find_chains(
    system: DistributionSystem, graph: nx.MultiGraph, source: str
) -> list[tuple[list[str], list[_Branch]]]:
    removable = {node for node in graph if _removable_bus(system, graph, node, source)}
    visited: set[str] = set()
    chains = []
    for endpoint in sorted(set(graph) - removable):
        for neighbor in sorted(graph.neighbors(endpoint)):
            if neighbor not in removable or neighbor in visited:
                continue
            nodes = [endpoint, neighbor]
            branches = [_branch_for_edge(system, next(iter(graph[endpoint][neighbor].values())))]
            current, previous = neighbor, endpoint
            while current in removable and current not in visited:
                visited.add(current)
                next_node = next(node for node in graph.neighbors(current) if node != previous)
                branches.append(
                    _branch_for_edge(system, next(iter(graph[current][next_node].values())))
                )
                nodes.append(next_node)
                previous, current = current, next_node
            valid_branches = [branch for branch in branches if branch is not None]
            if len(valid_branches) == len(branches):
                chains.append((nodes, valid_branches))
    return chains


def _series_asset_groups(system, assets, agg_time_series, time_series_type):
    asset_groups = []
    for asset_type in _ASSET_TYPES:
        group = [asset for asset in assets if type(asset) is asset_type]
        groups = (
            DistributionGenerator._group_for_aggregation(group, {})
            if asset_type is DistributionGenerator
            else [group]
        )
        for compatible in groups:
            if compatible:
                if agg_time_series:
                    _validate_aggregation_time_series(
                        system, asset_type, compatible, time_series_type
                    )
                asset_groups.append((asset_type, compatible))
    return asset_groups


def _merge_chain(
    system: DistributionSystem,
    nodes: list[str],
    branches: list[_Branch],
    distances: dict[str, float],
    equipment_updates: dict,
    equivalent_branches: list[_EquivalentBranch],
    agg_time_series: bool = False,
    time_series_type: type[TimeSeriesData] = SingleTimeSeries,
) -> None:
    endpoints = (nodes[0], nodes[-1])
    if endpoints[0] == endpoints[1]:
        return
    target_name = min(endpoints, key=lambda x: (distances.get(x, float("inf")), x))
    target = system.get_component(DistributionBus, target_name)
    assets = [
        parent
        for node in nodes[1:-1]
        for parent in system.list_parent_components(system.get_component(DistributionBus, node))
        if type(parent) in _ASSET_TYPES
    ]
    if any(
        not set(asset.phases).issubset(target.phases) or {Phase.S1, Phase.S2} & set(asset.phases)
        for asset in assets
    ):
        logger.warning("Keeping buses {}: asset phases are incompatible with endpoint", nodes)
        return

    asset_groups = _series_asset_groups(system, assets, agg_time_series, time_series_type)

    template = equivalent_branches[0]
    name = f"series_{uuid4()}"
    equipment = template.equipment.model_copy(
        deep=True,
        update={
            "uuid": uuid4(),
            "name": f"{name}_equipment",
            "ampacity": min(
                (branch.equipment.ampacity for branch in equivalent_branches),
                key=lambda value: value.to("ampere").magnitude,
            ),
            **equipment_updates,
        },
    )
    merged = template.model_copy(
        update={
            "uuid": uuid4(),
            "name": name,
            "in_service": True,
            "buses": [system.get_component(DistributionBus, node) for node in endpoints],
            "length": Distance(
                sum(branch.length.to("meter").magnitude for branch in equivalent_branches),
                "meter",
            ),
            "equipment": equipment,
        }
    )
    system.add_component(merged)
    for asset_type, compatible in asset_groups:
        combined = asset_type.aggregate(
            instances=compatible, bus=target, name=f"series_{uuid4()}", split_phase_mapping={}
        )
        if isinstance(combined, DistributionSolar):
            combined.inverter.rated_apparent_power = sum(
                solar.inverter.rated_apparent_power for solar in compatible
            )
        system.add_component(combined)
        if agg_time_series:
            _add_aggregated_time_series(
                system,
                system,
                asset_type,
                compatible,
                combined,
                time_series_type,
                _time_series_aggregators(),
                strict_time_series=True,
            )
        for asset in compatible:
            system.remove_component(asset, cascade_down=False)
    for branch in branches:
        system.remove_component(branch, cascade_down=False)
    for node in nodes[1:-1]:
        system.remove_component(system.get_component(DistributionBus, node), cascade_down=False)
