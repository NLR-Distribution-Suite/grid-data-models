import math
from io import StringIO
from uuid import uuid4

import numpy as np
import pytest
from loguru import logger

from gdm.quantities import (
    CapacitancePULength,
    Current,
    Distance,
    ReactancePULength,
    ResistancePULength,
    Voltage,
)
from gdm.systems.distribution.components import (
    DistributionBus,
    DistributionTransformer,
    DistributionVoltageSource,
    MatrixImpedanceBranch,
    MatrixImpedanceSwitch,
    SequenceImpedanceBranch,
)
from gdm.systems.distribution.components.geometry_branch import GeometryBranch
from gdm.systems.distribution.distribution_system import DistributionSystem
from gdm.systems.distribution.enums import Phase
from gdm.systems.distribution.equipment import MatrixImpedanceBranchEquipment
from gdm.systems.distribution.utils import electrical_distance_matrix
from tests.get_sample_system import get_three_bus_system


def _bus(name, phases=None):
    return DistributionBus(
        name=name,
        phases=phases or [Phase.A, Phase.B, Phase.C],
        rated_voltage=Voltage(10, "kilovolt"),
        voltage_type="line-to-line",
    )


def _branch(name, buses, r, x, phases=None, length=1):
    phases = phases or [Phase.A, Phase.B, Phase.C]
    r = np.atleast_2d(r)
    x = np.atleast_2d(x)
    equipment = MatrixImpedanceBranchEquipment(
        name=f"{name}-equipment",
        r_matrix=ResistancePULength(r, "ohm/km"),
        x_matrix=ReactancePULength(x, "ohm/km"),
        c_matrix=CapacitancePULength(np.eye(len(phases)), "nanofarad/km"),
        ampacity=Current(100, "ampere"),
    )
    return MatrixImpedanceBranch(
        name=name,
        buses=buses,
        phases=phases,
        length=Distance(length, "kilometer"),
        equipment=equipment,
    )


def _system(buses, branches=()):
    system = DistributionSystem(name="test-distance", auto_add_composed_components=True)
    source = DistributionVoltageSource.example().model_copy(
        update={"uuid": uuid4(), "bus": buses[0]}
    )
    system.add_components(*buses, source, *branches)
    return system


def test_radial_distance_complex_path_and_power_base():
    a, b, c = [_bus(name) for name in ("a", "b", "c")]
    first = _branch("first", [a, b], np.eye(3), np.eye(3) * 2, length=2)
    second = _branch("second", [b, c], np.eye(3) * 3, np.eye(3), length=1)
    system = _system([a, b, c], [first, second])

    result = electrical_distance_matrix(system)

    assert list(result.index) == list(result.columns) == ["a", "b", "c"]
    assert result.loc["a", "b"] == pytest.approx(abs(2 + 4j))
    assert result.loc["a", "c"] == pytest.approx(abs(5 + 5j))
    assert result.loc["c", "a"] == pytest.approx(result.loc["a", "c"])
    assert result.loc["b", "b"] == 0
    assert electrical_distance_matrix(system, base_mva=50).loc["a", "c"] == pytest.approx(
        abs(5 + 5j) / 2
    )
    assert system.get_component(MatrixImpedanceBranch, "first") is first


def test_partial_phase_and_positive_sequence_matrix():
    a, b, c = [_bus(name) for name in ("a", "b", "c")]
    r = np.full((3, 3), 0.5) + np.eye(3) * 1.5
    x = np.full((3, 3), 1.0) + np.eye(3) * 3.0
    full = _branch("full", [a, b], r, x)
    partial = _branch(
        "partial", [b, c], [[2, 0.5], [0.5, 4]], [[1, 0], [0, 3]], [Phase.A, Phase.B]
    )
    result = electrical_distance_matrix(_system([a, b, c], [full, partial]))
    assert result.loc["a", "b"] == pytest.approx(abs(1.5 + 3j))
    assert result.loc["b", "c"] == pytest.approx(abs(3 + 2j))


def test_distance_logging_reports_progress_and_phase_approximation():
    a, b = [_bus(name) for name in ("a", "b")]
    branch = _branch("partial", [a, b], [[2]], [[1]], [Phase.A])
    stream = StringIO()
    sink = logger.add(stream, level="DEBUG", format="{level.name} {message}")
    try:
        electrical_distance_matrix(_system([a, b], [branch]))
        electrical_distance_matrix(_system([_bus("single")]))
    finally:
        logger.remove(sink)

    output = stream.getvalue()
    assert "Calculating electrical distances for system test-distance" in output
    assert "Validated energized radial network: 2 buses, 1 edges, source a" in output
    assert "Reducing system to 2 primary buses" in output
    assert "Branch partial has incomplete phases" in output
    assert "Component partial series impedance:" in output
    assert "Electrical distance matrix complete: 2 primary buses" in output
    assert "Electrical distance matrix complete: 1 primary bus" in output


def test_neutral_reduction_for_partial_phase_branch():
    a, b = [_bus(name, [Phase.A, Phase.N]) for name in ("a", "b")]
    branch = _branch(
        "neutral",
        [a, b],
        [[4, 1], [1, 2]],
        [[2, 0.5], [0.5, 1]],
        [Phase.A, Phase.N],
    )
    result = electrical_distance_matrix(_system([a, b], [branch]))
    assert result.loc["a", "b"] == pytest.approx(abs(3.5 + 1.75j))


def test_sequence_impedance_uses_branch_length():
    branch = SequenceImpedanceBranch.example()
    for bus in branch.buses:
        bus.rated_voltage = Voltage(10, "kilovolt")
        bus.voltage_type = "line-to-line"
    result = electrical_distance_matrix(_system(branch.buses, [branch]))
    z_per_km = complex(
        branch.equipment.pos_seq_resistance.to("ohm/km").magnitude,
        branch.equipment.pos_seq_reactance.to("ohm/km").magnitude,
    )
    expected = abs(z_per_km) * branch.length.to("km").magnitude
    assert result.loc[branch.buses[0].name, branch.buses[1].name] == pytest.approx(expected)


def test_rejects_disconnected_and_parallel_paths():
    a, b, c = [_bus(name) for name in ("a", "b", "c")]
    line = _branch("first", [a, b], np.eye(3), np.eye(3))
    with pytest.raises(ValueError, match="disconnected"):
        electrical_distance_matrix(_system([a, b, c], [line]))
    parallel = _branch("parallel", [a, b], np.eye(3), np.eye(3))
    with pytest.raises(ValueError, match="radial"):
        electrical_distance_matrix(_system([a, b], [line, parallel]))


def test_single_bus_and_invalid_base():
    system = _system([_bus("source")])
    assert electrical_distance_matrix(system).loc["source", "source"] == 0
    with pytest.raises(ValueError, match="base_mva"):
        electrical_distance_matrix(system, base_mva=math.nan)


def test_geometry_is_not_converted_in_original_system():
    branch = GeometryBranch.example()
    for bus in branch.buses:
        bus.rated_voltage = Voltage(10, "kilovolt")
        bus.voltage_type = "line-to-line"
    system = _system(branch.buses, [branch])
    matrix = electrical_distance_matrix(system)
    assert matrix.loc[branch.buses[0].name, branch.buses[1].name] > 0
    assert system.get_component(GeometryBranch, branch.name) is branch


def test_transformer_impedance_and_automatic_primary_reduction():
    transformer = DistributionTransformer.example()
    primary, downstream = transformer.buses
    downstream.rated_voltage = Voltage(4.16, "kilovolt")
    transformer.equipment.windings[1].rated_voltage = Voltage(4.16, "kilovolt")
    secondary_transformer = DistributionTransformer.example()
    secondary = secondary_transformer.buses[1].model_copy(
        update={"name": "secondary", "uuid": uuid4()}
    )
    secondary_transformer = secondary_transformer.model_copy(
        update={
            "name": "secondary-transformer",
            "buses": [downstream, secondary],
            "equipment": secondary_transformer.equipment.model_copy(
                update={"name": "secondary-equipment"}
            ),
        }
    )
    secondary_transformer.equipment.windings[0].rated_voltage = Voltage(4.16, "kilovolt")
    system = _system([primary, downstream, secondary], [transformer, secondary_transformer])

    result = electrical_distance_matrix(system)

    assert set(result.index) == {primary.name, downstream.name}
    expected = abs(complex(2, 2.3) / 100 * 100 / 0.056)
    assert result.loc[primary.name, downstream.name] == pytest.approx(expected)
    assert system.get_component(DistributionBus, secondary.name) is secondary


def test_primary_reduction_removes_center_tapped_secondary_transformer():
    system = get_three_bus_system()
    primary = system.get_component(DistributionBus, "Bus-1")
    source = DistributionVoltageSource.example().model_copy(update={"bus": primary})
    system.add_component(source)

    result = electrical_distance_matrix(system)

    assert list(result.index) == ["Bus-1"]
    assert result.loc["Bus-1", "Bus-1"] == 0


def test_open_and_out_of_service_edges_do_not_create_parallel_paths():
    a, b = [_bus(name) for name in ("a", "b")]
    line = _branch("line", [a, b], np.eye(3), np.eye(3))
    offline = _branch("offline", [a, b], np.eye(3), np.eye(3))
    offline.in_service = False
    switch = MatrixImpedanceSwitch.example()
    switch.buses = [a, b]
    switch.is_closed = [False, False, False]
    system = _system([a, b], [line, offline, switch])

    result = electrical_distance_matrix(system)

    assert result.loc["a", "b"] == pytest.approx(abs(1 + 1j))
    assert system.get_component(MatrixImpedanceBranch, "offline") is offline


def test_out_of_service_edge_disconnects_primary_buses():
    a, b = [_bus(name) for name in ("a", "b")]
    line = _branch("offline", [a, b], np.eye(3), np.eye(3))
    line.in_service = False
    with pytest.raises(ValueError, match="disconnected"):
        electrical_distance_matrix(_system([a, b], [line]))


def test_out_of_service_bus_is_excluded_without_mutating_system():
    a, b, inactive = [_bus(name) for name in ("a", "b", "inactive")]
    inactive.in_service = False
    line = _branch("line", [a, b], np.eye(3), np.eye(3))
    isolated = _branch("isolated", [b, inactive], np.eye(3), np.eye(3))
    system = _system([a, b, inactive], [line, isolated])

    result = electrical_distance_matrix(system)

    assert list(result.index) == ["a", "b"]
    assert system.get_component(DistributionBus, "inactive") is inactive
    assert system.get_component(MatrixImpedanceBranch, "isolated") is isolated
