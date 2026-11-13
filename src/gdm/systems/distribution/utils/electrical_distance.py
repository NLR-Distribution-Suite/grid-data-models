"""Bus-level electrical distances on a radial primary distribution network."""

import math

import networkx as nx
import numpy as np
import pandas as pd
from loguru import logger

from gdm.systems.distribution.components.base.distribution_branch_base import (
    DistributionBranchBase,
)
from gdm.systems.distribution.components.base.distribution_transformer_base import (
    DistributionTransformerBase,
)
from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.systems.distribution.components.distribution_reactor import DistributionReactor
from gdm.systems.distribution.components.distribution_vsource import DistributionVoltageSource
from gdm.systems.distribution.components.geometry_branch import GeometryBranch
from gdm.systems.distribution.components.geometry_switch import GeometrySwitch
from gdm.systems.distribution.distribution_system import DistributionSystem
from gdm.systems.distribution.enums import Phase, VoltageTypes
from gdm.systems.distribution.equipment.base.matrix_impedance_branch_equipment_base import (
    MatrixImpedanceBranchEquipmentBase,
)
from gdm.systems.distribution.equipment.base.sequence_impedance_branch_equipment_base import (
    SequenceImpedanceBranchEquipmentBase,
)
from gdm.systems.distribution.model_reduction.reducer import reduce_to_primary_system


def _line_voltage_kv(bus: DistributionBus) -> float:
    voltage = float(bus.rated_voltage.to("kilovolt").magnitude)
    if bus.voltage_type == VoltageTypes.LINE_TO_GROUND:
        voltage *= math.sqrt(3)
    if not math.isfinite(voltage) or voltage <= 0:
        raise ValueError(f"Bus {bus.name!r} has an invalid voltage base.")
    return voltage


def _matrix_impedance(branch: DistributionBranchBase) -> complex:
    equipment = branch.equipment
    r = np.asarray(equipment.r_matrix.to("ohm/meter").magnitude, dtype=float)
    x = np.asarray(equipment.x_matrix.to("ohm/meter").magnitude, dtype=float)
    phases = getattr(branch, "conductor_phases", None) or branch.phases
    if len(phases) != len(set(phases)) or r.shape != (len(phases), len(phases)):
        raise ValueError(
            f"Branch {branch.name!r} has unsupported conductor phases or matrix shape."
        )
    z = r + 1j * x
    keep = [i for i, phase in enumerate(phases) if phase != Phase.N]
    neutral = [i for i, phase in enumerate(phases) if phase == Phase.N]
    if not keep:
        raise ValueError(f"Branch {branch.name!r} has no phase conductors.")
    if neutral:
        try:
            z = z[np.ix_(keep, keep)] - z[np.ix_(keep, neutral)] @ np.linalg.solve(
                z[np.ix_(neutral, neutral)], z[np.ix_(neutral, keep)]
            )
        except np.linalg.LinAlgError as exc:
            raise ValueError(f"Branch {branch.name!r} has a singular neutral impedance.") from exc
    remaining = [phases[i] for i in keep]
    if set(remaining) == {Phase.A, Phase.B, Phase.C}:
        order = [remaining.index(phase) for phase in (Phase.A, Phase.B, Phase.C)]
        a = np.exp(2j * np.pi / 3)
        vector = np.array([1, a**2, a])
        impedance = np.conjugate(vector) @ z[np.ix_(order, order)] @ vector / 3
    else:
        logger.debug(
            "Branch {} has incomplete phases {}; using mean phase self-impedance",
            branch.name,
            remaining,
        )
        impedance = np.mean(np.diag(z))
    return complex(impedance) * float(branch.length.to("meter").magnitude)


def _transformer_impedance(transformer: DistributionTransformerBase, base_mva: float) -> complex:
    equipment = transformer.equipment
    if equipment.is_center_tapped or len(equipment.windings) != 2 or len(transformer.buses) != 2:
        raise ValueError(f"Transformer {transformer.name!r} is not a two-winding transformer.")
    w1, w2 = equipment.windings
    if w1.num_phases != 3 or w2.num_phases != 3:
        raise ValueError(f"Transformer {transformer.name!r} must have three-phase windings.")
    if len(equipment.coupling_sequences) != 1 or set(equipment.coupling_sequences[0]) != {0, 1}:
        raise ValueError(f"Transformer {transformer.name!r} has invalid winding coupling.")
    power1 = float(w1.rated_power.to("megava").magnitude)
    power2 = float(w2.rated_power.to("megava").magnitude)
    if not math.isfinite(power1) or power1 <= 0 or not math.isclose(power1, power2, rel_tol=1e-3):
        raise ValueError(
            f"Transformer {transformer.name!r} has incompatible winding power ratings."
        )

    def voltage_ratio(winding, bus):
        voltage = float(winding.rated_voltage.to("kilovolt").magnitude)
        if winding.voltage_type == VoltageTypes.LINE_TO_GROUND:
            voltage *= math.sqrt(3)
        return voltage / _line_voltage_kv(bus)

    ratio1 = voltage_ratio(w1, transformer.buses[0])
    ratio2 = voltage_ratio(w2, transformer.buses[1])
    if not math.isfinite(ratio1) or not math.isclose(ratio1, ratio2, rel_tol=1e-3):
        raise ValueError(f"Transformer {transformer.name!r} has incompatible voltage bases.")
    z = complex(w1.resistance + w2.resistance, equipment.winding_reactances[0]) / 100
    return z * base_mva / power1 * ratio1**2


def _edge_impedance(component, base_mva: float, frequency_hz: float, soil_resistivity: float):
    if isinstance(component, DistributionTransformerBase):
        impedance = _transformer_impedance(component, base_mva)
    elif isinstance(component, DistributionBranchBase):
        if isinstance(component, (GeometryBranch, GeometrySwitch)):
            logger.debug("Converting geometry for component {}", component.name)
            component = component.to_matrix_representation(frequency_hz, soil_resistivity)
        if isinstance(component, DistributionReactor):
            z = complex(
                component.equipment.resistance.to("ohm").magnitude,
                component.equipment.reactance.to("ohm").magnitude,
            )
        elif isinstance(component.equipment, SequenceImpedanceBranchEquipmentBase):
            equipment = component.equipment
            z = complex(
                equipment.pos_seq_resistance.to("ohm/meter").magnitude,
                equipment.pos_seq_reactance.to("ohm/meter").magnitude,
            ) * float(component.length.to("meter").magnitude)
        elif isinstance(component.equipment, MatrixImpedanceBranchEquipmentBase):
            z = _matrix_impedance(component)
        else:
            raise ValueError(f"Unsupported impedance for component {component.name!r}.")
        voltage1, voltage2 = (_line_voltage_kv(bus) for bus in component.buses)
        if not math.isclose(voltage1, voltage2, rel_tol=1e-3):
            raise ValueError(f"Branch {component.name!r} has incompatible bus voltage bases.")
        impedance = z * base_mva / voltage1**2
    else:
        raise ValueError(f"Unsupported impedance for component {component.name!r}.")
    if not math.isfinite(impedance.real) or not math.isfinite(impedance.imag):
        raise ValueError(f"Component {component.name!r} has nonfinite impedance.")
    if impedance.real < 0 or impedance.imag < 0:
        raise ValueError(f"Component {component.name!r} has negative series impedance.")
    return impedance


def _energized_graph(system: DistributionSystem) -> nx.MultiGraph:
    graph = system.get_undirected_graph()
    graph.remove_nodes_from(
        bus.name for bus in system.get_components(DistributionBus) if not bus.in_service
    )
    graph.remove_edges_from(
        [
            (u, v, key)
            for u, v, key, data in graph.edges(keys=True, data=True)
            if not data["in_service"] or not data["is_closed"]
        ]
    )
    return graph


def _validate_tree(graph: nx.MultiGraph, source: str) -> None:
    if source not in graph:
        raise ValueError(f"Source bus {source!r} is not in service.")
    if not nx.is_connected(graph):
        raise ValueError("The energized system contains disconnected buses.")
    if graph.number_of_edges() != graph.number_of_nodes() - 1:
        raise ValueError("The energized system must be radial, without loops or parallel paths.")


def _validate_source_and_transformers(system: DistributionSystem) -> DistributionVoltageSource:
    sources = [
        source for source in system.get_components(DistributionVoltageSource) if source.in_service
    ]
    if len(sources) != 1:
        raise ValueError("The energized system must have exactly one voltage source.")
    for transformer in system.get_components(DistributionTransformerBase):
        if transformer.in_service and all(bus.in_service for bus in transformer.buses):
            if len({bus.name for bus in transformer.buses}) > 2:
                raise ValueError(f"Transformer {transformer.name!r} has more than two terminals.")
    return sources[0]


def _working_system(system: DistributionSystem) -> DistributionSystem:
    from gdm.systems.substation.components import TwoTerminalEquipment

    working = system.deepcopy()
    for source in list(working.get_components(DistributionVoltageSource)):
        if not source.in_service:
            working.remove_component(source, cascade_down=False)
    for component_type in (
        DistributionBranchBase,
        DistributionTransformerBase,
        TwoTerminalEquipment,
    ):
        for component in list(working.get_components(component_type)):
            if not getattr(component, "in_service", True) or any(
                not bus.in_service for bus in component.buses
            ):
                working.remove_component(component, cascade_down=False)
    for bus in list(working.get_components(DistributionBus)):
        if not bus.in_service:
            for parent in working.list_parent_components(bus):
                working.remove_component(parent, cascade_down=False, force=True)
            working.remove_component(bus, cascade_down=False, force=True)
    return working


def _primary_tree(system: DistributionSystem, source: str) -> nx.Graph:
    working = _working_system(system)
    primary_names = {
        bus.name
        for bus in working.get_components(DistributionBus)
        if bus.rated_voltage.to("kilovolt").magnitude > 1.0
    }
    if not primary_names:
        raise ValueError("The system has no primary buses rated above 1 kV.")
    if source not in primary_names:
        raise ValueError("The source bus is not retained by primary reduction.")
    logger.info("Reducing system to {} primary buses", len(primary_names))
    reduced = reduce_to_primary_system(
        working, name="electrical-distance-primary", agg_time_series=False
    )
    reduced_graph = _energized_graph(reduced)
    if set(reduced_graph) != primary_names:
        raise ValueError("Primary reduction did not retain all primary buses.")
    _validate_tree(reduced_graph, source)
    if len(reduced_graph) == 1:
        tree = nx.Graph()
        tree.add_node(source)
        return tree
    directed = reduced.get_directed_graph()
    if (
        set(directed.nodes) != set(reduced_graph.nodes)
        or directed.number_of_edges() != reduced_graph.number_of_edges()
    ):
        raise ValueError("The directed graph does not preserve the primary topology.")
    tree = nx.Graph()
    tree.add_nodes_from(reduced_graph.nodes)
    for u, v, data in directed.edges(data=True):
        component = reduced.get_component(data["type"], data["name"])
        tree.add_edge(u, v, component=component)
    return tree


def electrical_distance_matrix(
    system: DistributionSystem,
    base_mva: float = 100.0,
    frequency_hz: float = 60.0,
    soil_resistivity_ohm_m: float = 100.0,
) -> pd.DataFrame:
    """Return radial primary-bus electrical distances in per unit.

    The result contains buses retained by ``reduce_to_primary_system`` (rated above
    1 kV). Each entry is the magnitude of the sum of complex series impedances
    along the unique energized path. The default three-phase power base is 100 MVA.
    Incomplete phase matrices use the mean available phase self-impedance after
    neutral reduction; transformer taps are ignored. Transformer percentages are
    assumed to be on the first winding's rated power and voltage base.

    Open switches and out-of-service equipment are excluded. Disconnected or
    non-radial systems and unsupported impedance models raise ``ValueError``.
    The original system is not modified.
    """
    logger.info(
        "Calculating electrical distances for system {} (base={} MVA, frequency={} Hz, "
        "soil resistivity={} ohm-m)",
        system.name,
        base_mva,
        frequency_hz,
        soil_resistivity_ohm_m,
    )
    for name, value in (
        ("base_mva", base_mva),
        ("frequency_hz", frequency_hz),
        ("soil_resistivity_ohm_m", soil_resistivity_ohm_m),
    ):
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be finite and positive.")

    source = _validate_source_and_transformers(system)
    source_name = source.bus.name
    graph = _energized_graph(system)
    _validate_tree(graph, source_name)
    logger.info(
        "Validated energized radial network: {} buses, {} edges, source {}",
        graph.number_of_nodes(),
        graph.number_of_edges(),
        source_name,
    )

    if len(graph) == 1:
        if source.bus.rated_voltage.to("kilovolt").magnitude <= 1:
            raise ValueError("The system has no primary buses rated above 1 kV.")
        logger.info("Electrical distance matrix complete: 1 primary bus")
        return pd.DataFrame([[0.0]], index=[source_name], columns=[source_name])
    tree = _primary_tree(system, source_name)
    for _, _, data in tree.edges(data=True):
        data["impedance"] = _edge_impedance(
            data["component"], base_mva, frequency_hz, soil_resistivity_ohm_m
        )
        logger.debug(
            "Component {} series impedance: {} pu",
            data["component"].name,
            data["impedance"],
        )
    names = sorted(tree.nodes)
    indexes = {name: index for index, name in enumerate(names)}
    result = np.zeros((len(names), len(names)), dtype=float)
    for i, source in enumerate(names):
        path_impedances = {source: 0j}
        for parent, child in nx.dfs_edges(tree, source):
            path_impedances[child] = path_impedances[parent] + tree[parent][child]["impedance"]
            result[i, indexes[child]] = abs(path_impedances[child])
    logger.info("Electrical distance matrix complete: {} primary buses", len(names))
    return pd.DataFrame(result, index=names, columns=names)
