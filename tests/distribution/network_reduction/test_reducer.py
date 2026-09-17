from collections import Counter
from datetime import timedelta, datetime
from io import StringIO
from uuid import uuid4

import networkx as nx
import pytest
from loguru import logger

from infrasys import Component
from infrasys.time_series_models import SingleTimeSeries, NonSequentialTimeSeries

from gdm.distribution.model_reduction import (
    reduce_to_three_phase_system,
    reduce_to_primary_system,
    reduce_to_radial_network,
)
from gdm.distribution.sys_functools import (
    get_aggregated_load_time_series,
    get_aggregated_solar_time_series,
)
from gdm.distribution.components import (
    DistributionLoad,
    DistributionBus,
    DistributionSolar,
    DistributionVoltageSource,
)
from gdm.distribution.components.matrix_impedance_branch import MatrixImpedanceBranch
from gdm.distribution.components.matrix_impedance_switch import MatrixImpedanceSwitch
from gdm.distribution.enums import Phase, VoltageTypes
from gdm.distribution.equipment.matrix_impedance_branch_equipment import (
    MatrixImpedanceBranchEquipment,
)

from gdm.distribution.components.base.distribution_switch_base import DistributionSwitchBase
from gdm.distribution import DistributionSystem

from gdm.exceptions import (
    IncompatibleTimeSeries,
    UnsupportedVariableError,
    InconsistentTimeSeriesAggregation,
)
from gdm.quantities import (
    ActivePower,
    CapacitancePULength,
    Current,
    Distance,
    Irradiance,
    ReactancePULength,
    ResistancePULength,
    Voltage,
)


class CustomTimeSeries:
    "A dummy time series class for test"


def get_total_kw(load: DistributionLoad):
    return sum([item.real_power.to("megawatt").magnitude for item in load.equipment.phase_loads])


def get_total_kvar(load: DistributionLoad):
    return sum(
        [item.reactive_power.to("megavar").magnitude for item in load.equipment.phase_loads]
    )


def test_three_phase_network_reducer_with_single_timeseries(
    distribution_system_with_single_time_series,
):
    gdm_sys: DistributionSystem = distribution_system_with_single_time_series
    reduce_to_three_phase_system(
        gdm_sys, name="reduced_system", agg_time_series=True, time_series_type=SingleTimeSeries
    )


def test_three_phase_network_reducer_with_nonsequential_timeseries(
    distribution_system_with_nonsequential_time_series,
):
    gdm_sys: DistributionSystem = distribution_system_with_nonsequential_time_series
    reduce_to_three_phase_system(
        gdm_sys,
        name="reduced_system",
        agg_time_series=True,
        time_series_type=NonSequentialTimeSeries,
    )


def test_three_phase_network_reducer(distribution_system_with_single_time_series):
    gdm_sys: DistributionSystem = distribution_system_with_single_time_series
    reducer = reduce_to_three_phase_system(gdm_sys, name="reduced_system", agg_time_series=False)
    bus = list(reducer.get_components(DistributionBus))[0]

    split_phase_mapping = gdm_sys.get_split_phase_mapping()
    reducer_total_load = DistributionLoad.aggregate(
        list(reducer.get_components(DistributionLoad)),
        bus,
        "reducer_total",
        split_phase_mapping,
    )
    gdm_total_load = DistributionLoad.aggregate(
        list(gdm_sys.get_components(DistributionLoad)),
        bus,
        "gdm_total",
        split_phase_mapping,
    )
    assert get_total_kw(reducer_total_load) == get_total_kw(gdm_total_load), f"""Active power Reduced: {get_total_kw(reducer_total_load)} MW,
        Original: {get_total_kw(gdm_total_load)} MW"""

    assert get_total_kvar(reducer_total_load) == get_total_kvar(gdm_total_load), f"""Reactive power Reduced: {get_total_kvar(reducer_total_load)} Mvar,
        Original: {get_total_kvar(gdm_total_load)} Mvar"""


def test_three_phase_reducer_rejects_closed_loop(simple_distribution_system):
    system = simple_distribution_system.deepcopy()
    system.auto_add_composed_components = True
    _add_loop_switch(system, "bus_0", "bus_4", "test_switch_0_4")

    with pytest.raises(ValueError, match="run reduce_to_radial_network first"):
        reduce_to_three_phase_system(system, name="reduced_system")


def test_radial_then_three_phase_reduction_preserves_open_switch_and_load(
    simple_distribution_system,
):
    system = simple_distribution_system.deepcopy()
    system.auto_add_composed_components = True
    _add_loop_switch(system, "bus_0", "bus_4", "test_switch_0_4")

    radial = reduce_to_radial_network(system, name="radial_system")
    reduced = reduce_to_three_phase_system(radial, name="reduced_system")

    switch = reduced.get_component(MatrixImpedanceSwitch, "test_switch_0_4")
    assert switch.is_closed == [False, False, False]
    assert {bus.name for bus in switch.buses} == {"bus_0", "bus_4"}
    original_total = sum(
        power.to("megawatt").magnitude
        for load in system.get_components(DistributionLoad)
        for phase_load in load.equipment.phase_loads
        for power in [phase_load.real_power]
    )
    reduced_total = sum(
        power.to("megawatt").magnitude
        for load in reduced.get_components(DistributionLoad)
        for phase_load in load.equipment.phase_loads
        for power in [phase_load.real_power]
    )
    assert reduced_total == original_total


def test_incompatible_timeseries_and_unsupported_variable_error(
    distribution_system_with_nonsequential_time_series,
):
    """Test to raise error when incompatible timeseries is passed"""
    gdm_sys = distribution_system_with_nonsequential_time_series
    loads = list(gdm_sys.get_components(DistributionLoad))
    solars = list(gdm_sys.get_components(DistributionSolar))

    with pytest.raises(IncompatibleTimeSeries):
        get_aggregated_load_time_series(
            gdm_sys,
            loads,
            "active_power",
            time_series_type=CustomTimeSeries,
        )

    with pytest.raises(IncompatibleTimeSeries):
        get_aggregated_solar_time_series(
            gdm_sys,
            solars,
            "irradiance",
            time_series_type=CustomTimeSeries,
        )

    with pytest.raises(UnsupportedVariableError):
        get_aggregated_solar_time_series(
            gdm_sys,
            solars,
            "active_solar",
            time_series_type=SingleTimeSeries,
        )


def test_time_series_consistencies(simple_distribution_system):
    gdm_sys = simple_distribution_system
    load_profile_kw_1 = SingleTimeSeries.from_array(
        data=ActivePower([1, 2, 3, 4, 5], "kilowatt"),
        name="active_power",
        initial_timestamp=datetime(2020, 1, 1),
        resolution=timedelta(minutes=30),
    )
    load_profile_kw_2 = SingleTimeSeries.from_array(
        data=ActivePower([1, 2, 3, 4, 5, 6], "kilowatt"),
        name="active_power",
        initial_timestamp=datetime(2020, 1, 1),
        resolution=timedelta(minutes=30),
    )
    loads = list(gdm_sys.get_components(DistributionLoad))
    gdm_sys.add_time_series(
        load_profile_kw_2,
        loads[0],
        profile_type="PMult",
        profile_name="load_profile_kw",
        use_actual=True,
    )
    gdm_sys.add_time_series(
        load_profile_kw_1,
        *loads[1:],
        profile_type="PMult",
        profile_name="load_profile_kw",
        use_actual=True,
    )

    irradiance_profile_1 = SingleTimeSeries.from_array(
        data=Irradiance([0, 0.5, 1, 0.5, 0], "kilowatt / meter ** 2"),
        name="irradiance",
        initial_timestamp=datetime(2020, 1, 1),
        resolution=timedelta(minutes=30),
    )
    irradiance_profile_2 = SingleTimeSeries.from_array(
        data=Irradiance([0, 0.5, 0.8, 1, 0.5, 0], "kilowatt / meter ** 2"),
        name="irradiance",
        initial_timestamp=datetime(2020, 1, 1),
        resolution=timedelta(minutes=30),
    )
    pvs: list[DistributionSolar] = list(gdm_sys.get_components(DistributionSolar))
    gdm_sys.add_time_series(
        irradiance_profile_2,
        pvs[0],
        profile_type="PMult",
        profile_name="pv_profile",
        use_actual=False,
    )
    gdm_sys.add_time_series(
        irradiance_profile_1,
        *pvs[1:],
        profile_type="PMult",
        profile_name="pv_profile",
        use_actual=False,
    )
    with pytest.raises(InconsistentTimeSeriesAggregation):
        get_aggregated_load_time_series(
            gdm_sys,
            loads,
            "active_power",
            time_series_type=SingleTimeSeries,
        )
    with pytest.raises(InconsistentTimeSeriesAggregation):
        get_aggregated_solar_time_series(
            gdm_sys,
            pvs,
            "irradiance",
            time_series_type=SingleTimeSeries,
        )


def test_time_series_metadata_consistencies(simple_distribution_system):
    gdm_sys = simple_distribution_system
    load_profile_kw = SingleTimeSeries.from_array(
        data=ActivePower([1, 2, 3, 4, 5], "kilowatt"),
        name="active_power",
        initial_timestamp=datetime(2020, 1, 1),
        resolution=timedelta(minutes=30),
    )
    loads = list(gdm_sys.get_components(DistributionLoad))
    gdm_sys.add_time_series(
        load_profile_kw,
        loads[0],
        profile_type="PMult",
        profile_name="load_profile_kw",
        use_actual=True,
    )
    gdm_sys.add_time_series(
        load_profile_kw,
        *loads[1:],
        profile_type="PMult1",
        profile_name="load_profile_kw1",
        use_actual=True,
    )
    with pytest.raises(InconsistentTimeSeriesAggregation):
        get_aggregated_load_time_series(
            gdm_sys,
            loads,
            "active_power",
            time_series_type=SingleTimeSeries,
        )

    gdm_sys2 = simple_distribution_system
    load_profile_kw1 = NonSequentialTimeSeries.from_array(
        data=ActivePower([1, 2, 3, 4, 5], "kilowatt"),
        timestamps=[
            datetime(2020, 1, 1),
            datetime(2020, 1, 3),
            datetime(2020, 2, 1),
            datetime(2020, 2, 3),
            datetime(2020, 3, 1),
        ],
        name="active_power",
    )
    load_profile_kw2 = NonSequentialTimeSeries.from_array(
        data=ActivePower([1, 2, 3, 4, 5, 6], "kilowatt"),
        timestamps=[
            datetime(2020, 1, 1),
            datetime(2020, 1, 3),
            datetime(2020, 2, 1),
            datetime(2020, 2, 3),
            datetime(2020, 3, 1),
            datetime(2020, 3, 2),
        ],
        name="active_power",
    )
    loads = list(gdm_sys.get_components(DistributionLoad))
    gdm_sys2.add_time_series(
        load_profile_kw2,
        loads[0],
        profile_type="PMult",
        profile_name="load_profile_kw",
        use_actual=True,
    )
    gdm_sys2.add_time_series(
        load_profile_kw1,
        *loads[1:],
        profile_type="PMult1",
        profile_name="load_profile_kw1",
        use_actual=True,
    )
    with pytest.raises(InconsistentTimeSeriesAggregation):
        get_aggregated_load_time_series(
            gdm_sys2,
            loads,
            "active_power",
            time_series_type=NonSequentialTimeSeries,
        )


def test_time_series_unsupported_var(simple_distribution_system):
    gdm_sys = simple_distribution_system
    load_profile_kw = SingleTimeSeries.from_array(
        data=ActivePower([1, 2, 3, 4, 5], "kilowatt"),
        name="active_load",
        initial_timestamp=datetime(2020, 1, 1),
        resolution=timedelta(minutes=30),
    )
    loads = list(gdm_sys.get_components(DistributionLoad))
    gdm_sys.add_time_series(
        load_profile_kw,
        *loads,
        profile_type="PMult",
        profile_name="load_profile_kw",
        use_actual=False,
    )
    with pytest.raises(UnsupportedVariableError):
        get_aggregated_load_time_series(
            gdm_sys,
            loads,
            "active_load",
            time_series_type=SingleTimeSeries,
        )


def test_reduce_to_primary_system(distribution_system_with_single_time_series):
    gdm_sys: DistributionSystem = distribution_system_with_single_time_series
    reducer = reduce_to_primary_system(gdm_sys, name="reduced_system", agg_time_series=False)
    bus = list(reducer.get_components(DistributionBus))[0]

    split_phase_mapping = gdm_sys.get_split_phase_mapping()
    reducer_total_load = DistributionLoad.aggregate(
        list(reducer.get_components(DistributionLoad)),
        bus,
        "reducer_total",
        split_phase_mapping,
    )
    gdm_total_load = DistributionLoad.aggregate(
        list(gdm_sys.get_components(DistributionLoad)),
        bus,
        "gdm_total",
        split_phase_mapping,
    )
    assert get_total_kw(reducer_total_load) == get_total_kw(gdm_total_load), f"""Active power Reduced: {get_total_kw(reducer_total_load)} MW,
        Original: {get_total_kw(gdm_total_load)} MW"""

    assert get_total_kvar(reducer_total_load) == get_total_kvar(gdm_total_load), f"""Reactive power Reduced: {get_total_kvar(reducer_total_load)} Mvar,
        Original: {get_total_kvar(gdm_total_load)} Mvar"""


def test_reduce_to_primary_system_does_not_repeat_graph_logs(simple_distribution_system):
    gdm_sys: DistributionSystem = simple_distribution_system
    captured_messages: list[str] = []
    sink_id = logger.add(lambda message: captured_messages.append(message.record["message"]))

    try:
        reduce_to_primary_system(gdm_sys, name="reduced_system", agg_time_series=False)
    finally:
        logger.remove(sink_id)

    repeated_counts = Counter(captured_messages)
    repeated_graph_messages = {
        msg: count
        for msg, count in repeated_counts.items()
        if count > 1
        and (
            msg.startswith("Creating directed graph with source bus ->")
            or msg.startswith("The following buses have phases not connected to any component:")
        )
    }

    assert not repeated_graph_messages, (
        "Reducer should not repeatedly emit identical graph-construction warnings in a single "
        f"reduction run. Repeated messages: {repeated_graph_messages}"
    )


def _make_bus(name: str, phases: list[Phase], kv: float = 12.47) -> DistributionBus:
    return DistributionBus(
        name=name,
        rated_voltage=Voltage(kv, "kilovolt"),
        phases=phases,
        voltage_type=VoltageTypes.LINE_TO_LINE,
    )


def _three_phase_equipment() -> MatrixImpedanceBranchEquipment:
    return MatrixImpedanceBranchEquipment.example()


def _single_phase_equipment(name: str) -> MatrixImpedanceBranchEquipment:
    return MatrixImpedanceBranchEquipment(
        name=name,
        r_matrix=ResistancePULength([[0.0882]], "ohm/mi"),
        x_matrix=ReactancePULength([[0.2074]], "ohm/mi"),
        c_matrix=CapacitancePULength([[2.9]], "nanofarad/mi"),
        ampacity=Current(90, "ampere"),
    )


def _make_branch(
    name: str,
    bus_a: DistributionBus,
    bus_b: DistributionBus,
    phases: list[Phase],
    equipment: MatrixImpedanceBranchEquipment,
) -> MatrixImpedanceBranch:
    return MatrixImpedanceBranch(
        name=name,
        buses=[bus_a, bus_b],
        length=Distance(50, "meter"),
        phases=phases,
        equipment=equipment,
    )


def _build_phase_split_system() -> tuple[DistributionSystem, dict[str, DistributionBus]]:
    """Build a system where a 3ph corridor is split into three parallel 1ph buses."""
    sys = DistributionSystem(auto_add_composed_components=True)

    src = _make_bus("src_bus", [Phase.A, Phase.B, Phase.C])
    bus_x = _make_bus("bus_X", [Phase.A, Phase.B, Phase.C])
    bus_y = _make_bus("bus_Y", [Phase.A, Phase.B, Phase.C])
    imed_a = _make_bus("imed_A", [Phase.A])
    imed_b = _make_bus("imed_B", [Phase.B])
    imed_c = _make_bus("imed_C", [Phase.C])
    lat_bus = _make_bus("lat_bus", [Phase.A])

    for bus in (src, bus_x, bus_y, imed_a, imed_b, imed_c, lat_bus):
        sys.add_component(bus)

    three_ph_eq = _three_phase_equipment()
    sys.add_component(
        _make_branch("br_src_x", src, bus_x, [Phase.A, Phase.B, Phase.C], three_ph_eq)
    )

    for phase, imed in ((Phase.A, imed_a), (Phase.B, imed_b), (Phase.C, imed_c)):
        eq_up = _single_phase_equipment(f"eq_up_{phase.value}")
        eq_dn = _single_phase_equipment(f"eq_dn_{phase.value}")
        sys.add_component(_make_branch(f"br_x_{phase.value}", bus_x, imed, [phase], eq_up))
        sys.add_component(_make_branch(f"br_{phase.value}_y", imed, bus_y, [phase], eq_dn))

    sys.add_component(
        _make_branch(
            "br_lateral",
            bus_x,
            lat_bus,
            [Phase.A],
            _single_phase_equipment("eq_lateral"),
        )
    )

    sys.add_component(
        DistributionVoltageSource.example().model_copy(update={"bus": src, "name": "vsource"})
    )

    return sys, {
        "src": src,
        "bus_x": bus_x,
        "bus_y": bus_y,
        "imed_a": imed_a,
        "imed_b": imed_b,
        "imed_c": imed_c,
        "lat_bus": lat_bus,
    }



def test_three_phase_reduction_keeps_phase_split_intermediates():
    sys, buses = _build_phase_split_system()

    reduced = reduce_to_three_phase_system(sys, name="reduced", include_intermediate_buses=True)

    reduced_bus_names = {b.name for b in reduced.get_components(DistributionBus)}
    expected_kept = {
        buses["src"].name,
        buses["bus_x"].name,
        buses["bus_y"].name,
        buses["imed_a"].name,
        buses["imed_b"].name,
        buses["imed_c"].name,
    }
    assert reduced_bus_names == expected_kept
    assert buses["lat_bus"].name not in reduced_bus_names
def _add_loop_switch(system: DistributionSystem, bus_1: str, bus_2: str, name: str) -> None:
    """Add a closed switch between two buses, creating a loop."""
    switch = MatrixImpedanceSwitch.example()
    switch.buses = [
        system.get_component(DistributionBus, bus_1),
        system.get_component(DistributionBus, bus_2),
    ]
    switch.is_closed = [True, True, True]
    system.add_component(switch.model_copy(update={"uuid": uuid4(), "name": name}))


def _add_loop_line(
    system: DistributionSystem, bus_1: str, bus_2: str, length_m: float
) -> MatrixImpedanceBranch:
    """Add a line between two buses, creating a loop."""
    line = MatrixImpedanceBranch.example().model_copy(
        update={
            "uuid": uuid4(),
            "name": f"line_{bus_1}_{bus_2}",
            "buses": [
                system.get_component(DistributionBus, bus_1),
                system.get_component(DistributionBus, bus_2),
            ],
            "length": Distance(length_m, "meter"),
        }
    )
    system.add_component(line)
    return line


def _directed_graph_without_pruning_warnings(system: DistributionSystem) -> nx.DiGraph:
    """Run get_directed_graph and assert no edges were pruned from the DFS tree."""
    log_stream = StringIO()
    sink_id = logger.add(log_stream, level="WARNING")
    try:
        graph = system.get_directed_graph(return_radial_network=True)
    finally:
        logger.remove(sink_id)
    assert (
        "pruned from DFS tree" not in log_stream.getvalue()
    ), f"Unexpected pruning warnings:\n{log_stream.getvalue()}"
    return graph


def _export_and_reload(system: DistributionSystem, tmp_path) -> DistributionSystem:
    """Round-trip a system through JSON export/import."""
    path = tmp_path / "exported.json"
    system.to_json(path)
    return DistributionSystem.from_json(path)


def _equipment_signature(equipment) -> dict:
    # JSON mode serializes pint quantities and numpy matrices to plain values.
    return {
        key: value
        for key, value in equipment.model_dump(mode="json").items()
        if key not in {"name", "uuid", "controller"}
    }


def test_reduce_to_radial_opens_closed_switch(simple_distribution_system, tmp_path):
    system = simple_distribution_system.deepcopy()
    system.auto_add_composed_components = True
    _add_loop_switch(system, "bus_0", "bus_4", "test_switch_0_4")

    reduced = reduce_to_radial_network(system, name="radial_system")

    assert reduced.get_component(MatrixImpedanceSwitch, "test_switch_0_4").is_closed == [
        False,
        False,
        False,
    ]
    # The input system must not be mutated.
    assert system.get_component(MatrixImpedanceSwitch, "test_switch_0_4").is_closed == [
        True,
        True,
        True,
    ]

    graph = _directed_graph_without_pruning_warnings(reduced)
    assert graph.number_of_edges() == graph.number_of_nodes() - 1

    # The exported model must keep the property after a JSON round-trip.
    reloaded = _export_and_reload(reduced, tmp_path)
    radial_graph = _directed_graph_without_pruning_warnings(reloaded)
    assert radial_graph.number_of_edges() == radial_graph.number_of_nodes() - 1


def test_reduce_to_radial_converts_shortest_line(simple_distribution_system):
    system = simple_distribution_system.deepcopy()
    system.auto_add_composed_components = True
    _add_loop_line(system, "bus_2", "bus_6", length_m=50.0)

    reduced = reduce_to_radial_network(system, name="radial_system")

    switch = reduced.get_component(MatrixImpedanceSwitch, "line_bus_2_bus_6_switch")
    assert switch.is_closed == [False, False, False]
    assert switch.length.to("meter").magnitude == 50.0
    assert {bus.name for bus in switch.buses} == {"bus_2", "bus_6"}

    # The converted line must be gone from the reduced system.
    remaining_lines = [line.name for line in reduced.get_components(MatrixImpedanceBranch)]
    assert "line_bus_2_bus_6" not in remaining_lines

    original_line = system.get_component(MatrixImpedanceBranch, "line_bus_2_bus_6")
    assert _equipment_signature(switch.equipment) == _equipment_signature(original_line.equipment)

    _directed_graph_without_pruning_warnings(reduced)


def test_reduce_to_radial_tie_breaks_by_name(simple_distribution_system):
    system = simple_distribution_system.deepcopy()
    system.auto_add_composed_components = True
    # Same length as every fixture line, so all lines in the loop tie.
    _add_loop_line(system, "bus_2", "bus_6", length_m=130.2)

    reduced = reduce_to_radial_network(system, name="radial_system")

    # The lexicographically smallest line name in the loop is converted.
    remaining_lines = [line.name for line in reduced.get_components(MatrixImpedanceBranch)]
    assert "line_bus_2_bus_3" not in remaining_lines
    switch = reduced.get_component(MatrixImpedanceSwitch, "line_bus_2_bus_3_switch")
    assert switch.is_closed == [False, False, False]

    _directed_graph_without_pruning_warnings(reduced)


def test_reduce_to_radial_multiple_loops(simple_distribution_system):
    system = simple_distribution_system.deepcopy()
    system.auto_add_composed_components = True
    _add_loop_switch(system, "bus_0", "bus_4", "test_switch_1")
    _add_loop_switch(system, "bus_1", "bus_5", "test_switch_2")

    reduced = reduce_to_radial_network(system, name="radial_system")

    for switch_name in ("test_switch_1", "test_switch_2"):
        assert reduced.get_component(MatrixImpedanceSwitch, switch_name).is_closed == [
            False,
            False,
            False,
        ]

    graph = _directed_graph_without_pruning_warnings(reduced)
    assert graph.number_of_edges() == graph.number_of_nodes() - 1


def test_reduce_to_radial_already_radial(simple_distribution_system):
    system = simple_distribution_system.deepcopy()
    original_components = sorted(
        (type(component).__name__, component.name)
        for component in system.get_components(Component)
    )

    reduced = reduce_to_radial_network(system, name="radial_system")

    assert reduced.name == "radial_system"
    reduced_components = sorted(
        (type(component).__name__, component.name)
        for component in reduced.get_components(Component)
    )
    assert original_components == reduced_components

    _directed_graph_without_pruning_warnings(reduced)


def test_reduce_to_radial_is_deterministic(simple_distribution_system):
    def build_and_reduce() -> DistributionSystem:
        system = simple_distribution_system.deepcopy()
        system.auto_add_composed_components = True
        _add_loop_switch(system, "bus_0", "bus_4", "test_switch_1")
        _add_loop_line(system, "bus_2", "bus_6", length_m=50.0)
        return reduce_to_radial_network(system, name="radial_system")

    reduced_a = build_and_reduce()
    reduced_b = build_and_reduce()

    def signature(system: DistributionSystem):
        components = {
            (type(component).__name__, component.name)
            for component in system.get_components(Component)
        }
        switches = {
            (switch.name, tuple(switch.is_closed))
            for switch in system.get_components(DistributionSwitchBase)
        }
        graph = system.get_undirected_graph()
        edges = {(min(u, v), max(u, v), data["name"]) for u, v, data in graph.edges(data=True)}
        return components, switches, edges

    assert signature(reduced_a) == signature(reduced_b)


def test_reduce_to_radial_preserves_time_series(
    distribution_system_with_single_time_series,
):
    system = distribution_system_with_single_time_series.deepcopy()
    system.auto_add_composed_components = True
    _add_loop_switch(system, "bus_0", "bus_4", "test_switch_1")

    reduced = reduce_to_radial_network(system, name="radial_system")

    original_loads = {load.name for load in system.get_components(DistributionLoad)}
    reduced_loads = {load.name for load in reduced.get_components(DistributionLoad)}
    assert original_loads == reduced_loads
    for load_name in sorted(original_loads):
        original_ts = [
            metadata.name
            for metadata in system.list_time_series_metadata(
                system.get_component(DistributionLoad, load_name)
            )
        ]
        reduced_ts = [
            metadata.name
            for metadata in reduced.list_time_series_metadata(
                reduced.get_component(DistributionLoad, load_name)
            )
        ]
        assert original_ts == reduced_ts

    _directed_graph_without_pruning_warnings(reduced)
