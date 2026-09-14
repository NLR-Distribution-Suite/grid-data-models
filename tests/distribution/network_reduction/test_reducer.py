from collections import Counter
from datetime import timedelta, datetime
import pytest
from loguru import logger

from infrasys.time_series_models import SingleTimeSeries, NonSequentialTimeSeries

from gdm.distribution.model_reduction import reduce_to_three_phase_system, reduce_to_primary_system
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
from gdm.distribution.enums import Phase, VoltageTypes
from gdm.distribution.equipment.matrix_impedance_branch_equipment import (
    MatrixImpedanceBranchEquipment,
)
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


def test_three_phase_reduction_excludes_intermediates_by_default():
    sys, buses = _build_phase_split_system()

    reduced = reduce_to_three_phase_system(sys, name="reduced")

    reduced_bus_names = {b.name for b in reduced.get_components(DistributionBus)}
    assert reduced_bus_names == {buses["src"].name, buses["bus_x"].name, buses["bus_y"].name}


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
