"""Radial distribution network reduction."""

import uuid
from typing import Callable

import networkx as nx

from gdm.hashing_utils import remove_unreferenced_equipment
from gdm.systems.distribution.components.base.distribution_branch_base import (
    DistributionBranchBase,
)
from gdm.systems.distribution.components.base.distribution_switch_base import (
    DistributionSwitchBase,
)
from gdm.systems.distribution.components.geometry_branch import GeometryBranch
from gdm.systems.distribution.components.matrix_impedance_branch import MatrixImpedanceBranch
from gdm.systems.distribution.components.matrix_impedance_switch import MatrixImpedanceSwitch
from gdm.systems.distribution.distribution_system import DistributionSystem
from gdm.systems.distribution.equipment.matrix_impedance_switch_equipment import (
    MatrixImpedanceSwitchEquipment,
)
from gdm.systems.distribution.model_reduction.common import _closed_edge_graph


def _normalize_cycle(cycle: list[str]) -> tuple[str, ...]:
    """Rotate a cycle so that it starts at its lexicographically smallest bus."""
    start = min(range(len(cycle)), key=cycle.__getitem__)
    return tuple(cycle[start:] + cycle[:start])


def _cycle_components(
    system: DistributionSystem,
    cycle: tuple[str, ...],
    graph: nx.MultiGraph,
    is_candidate: Callable[[type], bool],
) -> list[DistributionBranchBase]:
    """Resolve the branch components on a cycle that match ``is_candidate``.

    Components are deduplicated and returned sorted by name so that any
    downstream selection is deterministic.
    """
    seen: dict[uuid.UUID, DistributionBranchBase] = {}
    for i in range(len(cycle)):
        bus_1, bus_2 = cycle[i], cycle[(i + 1) % len(cycle)]
        if not graph.has_edge(bus_1, bus_2):
            continue
        for data in graph[bus_1][bus_2].values():
            component_type = data["type"]
            if is_candidate(component_type):
                component = system.get_component(component_type, data["name"])
                seen.setdefault(component.uuid, component)
    return sorted(seen.values(), key=lambda component: component.name)


def _switch_equipment_from_branch(
    line: DistributionBranchBase,
) -> MatrixImpedanceSwitchEquipment:
    """Build switch equipment from a branch's impedance data."""
    equipment_uuid = uuid.uuid5(uuid.NAMESPACE_URL, f"gdm.radial_switch_equipment.{line.uuid}")
    if isinstance(line, GeometryBranch):
        line = line.to_matrix_representation(frequency_hz=60)
    if not isinstance(line, MatrixImpedanceBranch):
        msg = (
            f"Cannot convert {line.__class__.__name__} to a switch. Only "
            "MatrixImpedanceBranch and GeometryBranch lines are supported."
        )
        raise ValueError(msg)
    return MatrixImpedanceSwitchEquipment(
        uuid=equipment_uuid, **line.equipment.model_dump(exclude_none=True, exclude={"uuid"})
    )


def _convert_line_to_open_switch(
    system: DistributionSystem, line: DistributionBranchBase
) -> MatrixImpedanceSwitch:
    """Replace ``line`` with an open switch between the same buses."""
    name = f"{line.name}_switch"
    existing_names = {switch.name for switch in system.get_components(MatrixImpedanceSwitch)}
    suffix = 1
    while name in existing_names:
        suffix += 1
        name = f"{line.name}_switch_{suffix}"

    switch = MatrixImpedanceSwitch(
        buses=line.buses,
        length=line.length,
        phases=list(line.phases),
        substation=line.substation,
        feeder=line.feeder,
        name=name,
        is_closed=[False] * len(line.phases),
        equipment=_switch_equipment_from_branch(line),
        uuid=uuid.uuid5(uuid.NAMESPACE_URL, f"gdm.radial_switch.{name}"),
    )
    system.remove_component(line)
    system.add_component(switch)
    return switch


def reduce_to_radial_network(dist_system: DistributionSystem, name: str) -> DistributionSystem:
    """Reduce a looped distribution system to a radial network.

    Every electrical loop in the input is broken deterministically: if a loop
    contains a closed switch, that switch is opened; otherwise the shortest
    line on the loop (ties broken by component name) is replaced with an open
    ``MatrixImpedanceSwitch`` between the same buses. The input system is not
    modified; a reduced copy is returned.

    Parameters
    ----------
    dist_system : DistributionSystem
        Source distribution system, possibly containing loops. Must be a single
        connected component fed from one voltage source (the same requirement
        as ``get_source_bus``).
    name : str
        Name of the reduced system.

    Returns
    -------
    DistributionSystem
        A radial copy of the input system in which no closed loop remains, so
        that ``get_directed_graph`` prunes no edges and emits no "pruned from
        DFS tree" warnings.

    Notes
    -----
    - Geometry-based lines are converted to their matrix representation at
      60 Hz when they are selected for conversion.
    - Only cycle edges are touched, so the reduced network stays connected.
    """
    system = dist_system.deepcopy()
    system.name = name
    closed_graph = _closed_edge_graph(system)

    while True:
        cycles = sorted(
            _normalize_cycle(cycle) for cycle in DistributionSystem.get_cycles(closed_graph)
        )
        if not cycles:
            break
        cycle = cycles[0]

        switches = _cycle_components(
            system, cycle, closed_graph, lambda t: issubclass(t, DistributionSwitchBase)
        )
        if switches:
            switch = switches[0]
            switch.is_closed = [False] * switch.num_conductors
            bus_1, bus_2 = switch.buses[0].name, switch.buses[1].name
            for key in [
                k for k, data in closed_graph[bus_1][bus_2].items() if data["name"] == switch.name
            ]:
                closed_graph.remove_edge(bus_1, bus_2, key=key)
            continue

        lines = _cycle_components(
            system,
            cycle,
            closed_graph,
            lambda t: (
                issubclass(t, DistributionBranchBase) and not issubclass(t, DistributionSwitchBase)
            ),
        )
        if not lines:
            msg = (
                f"Cycle {list(cycle)} contains no branches or switches that can be "
                "opened to break the loop; cannot reduce the system to a radial network."
            )
            raise ValueError(msg)

        line = min(lines, key=lambda b: (b.length.to("meter").magnitude, b.name))
        _convert_line_to_open_switch(system, line)
        bus_1, bus_2 = line.buses[0].name, line.buses[1].name
        for key in [
            k for k, data in closed_graph[bus_1][bus_2].items() if data["name"] == line.name
        ]:
            closed_graph.remove_edge(bus_1, bus_2, key=key)

    return remove_unreferenced_equipment(system)
