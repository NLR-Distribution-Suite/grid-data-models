from collections import Counter
from datetime import timedelta, datetime
from io import StringIO
from uuid import uuid4

import networkx as nx
import pytest
from loguru import logger

from infrasys import Component
from infrasys.base_quantity import ureg
from infrasys.time_series_models import SingleTimeSeries, NonSequentialTimeSeries

from gdm.hashing_utils import remove_unreferenced_equipment
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
from gdm.systems.distribution.components.distribution_battery import DistributionBattery
from gdm.systems.distribution.components.distribution_capacitor import DistributionCapacitor
from gdm.systems.distribution.components.distribution_generator import (
    DistributionGenerator,
    GeneratorOperatingMode,
)
from gdm.systems.distribution.components.distribution_transformer import DistributionTransformer
from gdm.systems.distribution.model_reduction.minimal import (
    _nearest_retained_buses,
    _series_lateral_with_consistant_buses,
    reduce_to_minimal_system_with_sw,
)
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
from gdm.systems.distribution.equipment import LoadEquipment
from gdm.systems.distribution.model_reduction import minimal, primary, radial, three_phase, trivial


class CustomTimeSeries:
    "A dummy time series class for test"


@pytest.mark.parametrize(
    ("module", "reducer", "force_no_trivial_nodes"),
    [
        (primary, lambda system: primary.reduce_to_primary_system(system, "reduced"), False),
        (
            three_phase,
            lambda system: three_phase.reduce_to_three_phase_system(system, "reduced"),
            False,
        ),
        (radial, lambda system: radial.reduce_to_radial_network(system, "reduced"), False),
        (trivial, lambda system: trivial.reduce_trivial_nodes(system), False),
        (trivial, lambda system: trivial.reduce_trivial_nodes(system), True),
        (minimal, lambda system: minimal.reduce_to_minimal_system_with_sw(system), False),
        (
            minimal,
            lambda system: minimal.reduce_to_minimal_system_with_sw(
                system, reduce_series_laterals=True
            ),
            False,
        ),
    ],
)
def test_reducers_clean_unreferenced_equipment(
    simple_distribution_system, monkeypatch, module, reducer, force_no_trivial_nodes
):
    orphan = LoadEquipment.example()
    cleanup_calls = []

    def cleanup_with_orphan(system):
        system.add_component(orphan)
        cleanup_calls.append(system)
        return remove_unreferenced_equipment(system)

    monkeypatch.setattr(module, "remove_unreferenced_equipment", cleanup_with_orphan)
    if force_no_trivial_nodes:
        monkeypatch.setattr(trivial, "_find_trivial_buses", lambda *args: set())

    reduced = reducer(simple_distribution_system)

    assert len(cleanup_calls) == 1
    assert cleanup_calls[0].has_component(orphan)
    assert not reduced.has_component(orphan)
    assert not simple_distribution_system.has_component(orphan)


def test_series_lateral_aggregates_assets_and_weighted_impedance():
    from tests.conftest import (
        build_distribution_buses,
        build_distribution_line,
        build_distribution_load,
        build_distribution_voltage_source,
    )

    buses = build_distribution_buses()[:4]
    system = DistributionSystem(auto_add_composed_components=True)
    system.add_components(*buses)
    system.add_component(build_distribution_voltage_source(buses[0]))
    branches = [build_distribution_line(buses[i], buses[i + 1]) for i in range(3)]
    for branch, length, factor, amps in zip(branches, [1, 2, 3], [1, 2, 4], [100, 50, 80]):
        branch.feeder = branches[0].feeder
        branch.substation = branches[0].substation
        branch.length = Distance(length, "meter")
        branch.equipment = branch.equipment.model_copy(
            update={
                "uuid": uuid4(),
                "name": str(uuid4()),
                "ampacity": Current(amps, "ampere"),
                "r_matrix": branch.equipment.r_matrix * factor,
                "x_matrix": branch.equipment.x_matrix * factor,
                "c_matrix": branch.equipment.c_matrix * factor,
            }
        )
        system.add_component(branch)
    load = build_distribution_load(buses[1], 1)
    system.add_component(load)
    original_power = get_total_kw(load)
    initial_matrix = branches[0].equipment.r_matrix

    graph = _series_lateral_with_consistant_buses(system, system.get_undirected_graph())

    assert set(graph) == {buses[0].name, buses[3].name}
    merged = list(system.get_components(MatrixImpedanceBranch))
    assert len(merged) == 1
    assert merged[0].length.to("meter").magnitude == pytest.approx(6)
    assert merged[0].equipment.ampacity.to("ampere").magnitude == pytest.approx(50)
    assert merged[0].equipment.r_matrix.to(initial_matrix.units).magnitude == pytest.approx(
        initial_matrix.magnitude * (17 / 6)
    )
    loads = list(system.get_components(DistributionLoad))
    assert len(loads) == 1
    assert loads[0].bus.name == buses[0].name
    assert get_total_kw(loads[0]) == pytest.approx(original_power)


def test_series_lateral_converts_geometry_to_matrix():
    from gdm.systems.distribution.components.geometry_branch import GeometryBranch
    from tests.conftest import build_distribution_buses, build_distribution_voltage_source

    buses = build_distribution_buses()[:3]
    system = DistributionSystem(auto_add_composed_components=True)
    system.add_components(*buses)
    system.add_component(build_distribution_voltage_source(buses[0]))
    example = GeometryBranch.example()
    branches = [
        example.model_copy(
            update={"uuid": uuid4(), "name": f"geometry_{i}", "buses": buses[i : i + 2]}
        )
        for i in range(2)
    ]
    for branch in branches:
        system.add_component(branch)
    expected = branches[0].to_matrix_representation()

    graph = _series_lateral_with_consistant_buses(system, system.get_undirected_graph())

    assert set(graph) == {buses[0].name, buses[2].name}
    assert list(system.get_components(GeometryBranch)) == []
    merged = next(system.get_components(MatrixImpedanceBranch))
    assert merged.length.to("meter").magnitude == pytest.approx(
        sum(branch.length.to("meter").magnitude for branch in branches)
    )
    assert merged.equipment.r_matrix.to(
        expected.equipment.r_matrix.units
    ).magnitude == pytest.approx(expected.equipment.r_matrix.magnitude)


def test_series_lateral_keeps_different_bus_phases():
    from tests.conftest import (
        build_distribution_buses,
        build_distribution_line,
        build_distribution_voltage_source,
    )

    buses = build_distribution_buses()[:3]
    buses[1].phases = [Phase.A]
    system = DistributionSystem(auto_add_composed_components=True)
    system.add_components(*buses)
    system.add_component(build_distribution_voltage_source(buses[0]))
    for i in range(2):
        system.add_component(build_distribution_line(buses[i], buses[i + 1]))
    graph = system.get_undirected_graph()

    reduced = _series_lateral_with_consistant_buses(system, graph)

    assert set(reduced) == set(graph)
    assert reduced.number_of_edges() == graph.number_of_edges()


@pytest.mark.parametrize("protected", ["branch", "asset"])
def test_series_lateral_keeps_out_of_service_boundaries(protected):
    from tests.conftest import (
        build_distribution_buses,
        build_distribution_line,
        build_distribution_load,
        build_distribution_voltage_source,
    )

    buses = build_distribution_buses()[:3]
    system = DistributionSystem(auto_add_composed_components=True)
    system.add_components(*buses)
    system.add_component(build_distribution_voltage_source(buses[0]))
    branches = [build_distribution_line(buses[i], buses[i + 1]) for i in range(2)]
    branches[1].feeder = branches[0].feeder
    branches[1].substation = branches[0].substation
    if protected == "branch":
        branches[0].in_service = False
    else:
        asset = build_distribution_load(buses[1], 1)
        asset.in_service = False
        system.add_component(asset)
    system.add_components(*branches)

    reduced = _series_lateral_with_consistant_buses(system, system.get_undirected_graph())

    assert set(reduced) == {bus.name for bus in buses}
    assert reduced.number_of_edges() == 2


@pytest.mark.parametrize("reduce_series_laterals", [False, True])
def test_minimal_reduction_aggregates_removed_loads_and_preserves_source(reduce_series_laterals):
    from tests.conftest import (
        build_distribution_buses,
        build_distribution_capacitor,
        build_distribution_line,
        build_distribution_load,
        build_distribution_voltage_source,
    )

    buses = [
        bus.model_copy(update={"rated_voltage": Voltage(12.47, "kilovolt")})
        for bus in build_distribution_buses()[:6]
    ]
    system = DistributionSystem(auto_add_composed_components=True)
    system.add_components(*buses)
    system.add_component(build_distribution_voltage_source(buses[0]))
    branches = [
        build_distribution_line(buses[i], buses[j]) for i, j in [(0, 1), (1, 2), (3, 4), (4, 5)]
    ]
    for branch in branches:
        branch.feeder = branches[0].feeder
        branch.substation = branches[0].substation
        system.add_component(branch)
    switch = MatrixImpedanceSwitch.example().model_copy(update={"buses": [buses[2], buses[3]]})
    system.add_component(switch)
    loads = [build_distribution_load(buses[i], i) for i in (3, 4, 5)]
    system.add_components(*loads)
    capacitor = build_distribution_capacitor(buses[4], 4)
    system.add_component(capacitor)

    original_graph = system.get_undirected_graph()
    reduced = reduce_to_minimal_system_with_sw(system, reduce_series_laterals)
    reduced_graph = reduced.get_undirected_graph()

    assert set(original_graph) == {bus.name for bus in buses}
    expected_buses = [buses[0], buses[2], buses[3]] if reduce_series_laterals else buses[:4]
    assert set(reduced_graph) == {bus.name for bus in expected_buses}
    assert {bus.name for bus in reduced.get_components(DistributionBus)} == set(reduced_graph)
    assert reduced.get_source_bus().name == buses[0].name
    assert reduced.has_component(switch)
    reduced_loads = list(reduced.get_components(DistributionLoad))
    assert all(load.bus.name == buses[3].name for load in reduced_loads)
    assert sum(get_total_kw(load) for load in reduced_loads) == pytest.approx(
        sum(get_total_kw(load) for load in loads)
    )
    assert sum(get_total_kvar(load) for load in reduced_loads) == pytest.approx(
        sum(get_total_kvar(load) for load in loads)
    )
    reduced_capacitor = next(reduced.get_components(DistributionCapacitor))
    assert reduced_capacitor.bus.name == buses[3].name
    assert sum(
        phase.rated_reactive_power.to("kvar").magnitude
        for phase in reduced_capacitor.equipment.phase_capacitors
    ) == pytest.approx(
        sum(
            phase.rated_reactive_power.to("kvar").magnitude
            for phase in capacitor.equipment.phase_capacitors
        )
    )


def test_minimal_reduction_assigns_nearest_retained_bus_deterministically():
    graph = nx.Graph([("a", "middle"), ("z", "middle"), ("z", "near_z")])
    targets, _ = _nearest_retained_buses(graph, {"z", "a"})

    assert targets["middle"] == "a"
    assert targets["near_z"] == "z"


def _minimal_time_series_system(time_series_type, multipliers=False, mismatched_timestamps=False):
    from tests.conftest import (
        build_distribution_buses,
        build_distribution_line,
        build_distribution_load,
        build_distribution_voltage_source,
        build_distribution_xfmr,
    )

    buses = [
        bus.model_copy(update={"rated_voltage": Voltage(12.47, "kilovolt")})
        for bus in build_distribution_buses()[:7]
    ]
    buses[6].rated_voltage = Voltage(0.4, "kilovolt")
    system = DistributionSystem(auto_add_composed_components=True)
    system.add_components(*buses)
    system.add_component(build_distribution_voltage_source(buses[0]))
    branches = [
        build_distribution_line(buses[i], buses[j]) for i, j in [(0, 1), (1, 2), (2, 3), (2, 5)]
    ]
    for branch in branches:
        branch.feeder = branches[0].feeder
        branch.substation = branches[0].substation
        system.add_component(branch)
    system.add_component(build_distribution_xfmr(buses[5], buses[6]))
    system.add_component(
        MatrixImpedanceSwitch.example().model_copy(update={"buses": [buses[3], buses[4]]})
    )
    loads = {}
    for bus_index, values in ((0, [7, 8]), (1, [5, 6]), (5, [3, 4]), (6, [1, 2])):
        load = build_distribution_load(buses[bus_index], bus_index)
        system.add_component(load)
        kwargs = {
            "data": (
                ureg.Quantity([0.5, 1], "dimensionless")
                if multipliers
                else ActivePower(values, "kilowatt")
            ),
            "name": "active_power",
        }
        if time_series_type is SingleTimeSeries:
            kwargs.update(initial_timestamp=datetime(2020, 1, 1), resolution=timedelta(hours=1))
        else:
            kwargs["timestamps"] = [
                datetime(2020, 1, 1),
                datetime(2020, 1, 3 if mismatched_timestamps and bus_index == 1 else 2),
            ]
        profile = time_series_type.from_array(**kwargs)
        system.add_time_series(
            profile, load, profile_type="PMult", profile_name="profile", use_actual=not multipliers
        )
        loads[bus_index] = load
    return system, buses, loads


@pytest.mark.parametrize("reduce_series_laterals", [False, True])
@pytest.mark.parametrize("agg_time_series", [False, True])
def test_minimal_retains_outages_and_secondary_topology(reduce_series_laterals, agg_time_series):
    from tests.conftest import (
        build_distribution_capacitor,
        build_distribution_load,
        build_distribution_solar,
    )

    system, buses, loads = _minimal_time_series_system(SingleTimeSeries)
    inactive_load = build_distribution_load(buses[6], 99)
    inactive_solar = build_distribution_solar(buses[5], 99)
    inactive_capacitor = build_distribution_capacitor(buses[5], 99)
    inactive_generator = DistributionGenerator.example().model_copy(
        update={"uuid": uuid4(), "name": "inactive_generator", "bus": buses[6]}
    )
    inactive_battery = DistributionBattery.example().model_copy(
        update={"uuid": uuid4(), "name": "inactive_battery", "bus": buses[6]}
    )
    assets = [
        inactive_load,
        inactive_solar,
        inactive_capacitor,
        inactive_generator,
        inactive_battery,
    ]
    for asset in assets:
        asset.in_service = False
        system.add_component(asset)
    inactive_branch = system.get_component(MatrixImpedanceBranch, "line_bus_2_bus_5")
    inactive_branch.in_service = False
    buses[6].in_service = False
    transformer = system.get_component(DistributionTransformer, "substation_xfmr")
    profile = SingleTimeSeries.from_array(
        data=ActivePower([11, 12], "kilowatt"),
        name="active_power",
        initial_timestamp=datetime(2020, 1, 1),
        resolution=timedelta(hours=1),
    )
    system.add_time_series(
        profile, inactive_load, profile_type="PMult", profile_name="outage", use_actual=True
    )

    reduced = reduce_to_minimal_system_with_sw(
        system,
        reduce_series_laterals=reduce_series_laterals,
        agg_time_series=agg_time_series,
        retain_out_of_service=True,
    )

    for component in [*assets, inactive_branch, buses[6], transformer]:
        assert reduced.has_component(component)
    assert not reduced.get_component(DistributionBus, buses[6].name).in_service
    assert not reduced.get_component(MatrixImpedanceBranch, inactive_branch.name).in_service
    for asset in assets:
        retained = reduced.get_component(type(asset), asset.name)
        assert retained.uuid == asset.uuid
        assert retained.bus.name == asset.bus.name
        assert not retained.in_service
    assert reduced.has_time_series(inactive_load) is agg_time_series
    if agg_time_series:
        saved = reduced.get_time_series(
            inactive_load,
            "active_power",
            profile_type="PMult",
            profile_name="outage",
            use_actual=True,
        )
        assert saved.data.to("kilowatt").magnitude == pytest.approx([11, 12])
    assert sum(
        get_total_kw(load) for load in reduced.get_components(DistributionLoad) if load.in_service
    ) == pytest.approx(sum(get_total_kw(load) for load in loads.values()))
    assert system.has_component(inactive_load)
    assert not inactive_load.in_service


def test_minimal_default_does_not_retain_outages_on_removed_buses():
    from tests.conftest import build_distribution_load

    system, buses, _ = _minimal_time_series_system(SingleTimeSeries)
    inactive = build_distribution_load(buses[6], 99)
    inactive.in_service = False
    system.add_component(inactive)
    reduced = reduce_to_minimal_system_with_sw(system)
    assert not reduced.has_component(inactive)
    assert system.has_component(inactive)


def test_minimal_retains_outages_behind_open_switch():
    from tests.conftest import build_distribution_load

    system, buses, _ = _minimal_time_series_system(SingleTimeSeries)
    switch = next(system.get_components(MatrixImpedanceSwitch))
    switch.is_closed = [False] * 3
    inactive = build_distribution_load(buses[4], 99)
    inactive.in_service = False
    system.add_component(inactive)

    reduced = reduce_to_minimal_system_with_sw(system, retain_out_of_service=True)

    assert reduced.has_component(inactive)
    assert reduced.has_component(switch)
    assert reduced.get_component(MatrixImpedanceSwitch, switch.name).is_closed == [False] * 3
    assert reduced.get_component(DistributionLoad, inactive.name).bus.name == buses[4].name


def test_minimal_retains_outage_through_secondary_path():
    from tests.conftest import (
        build_distribution_buses,
        build_distribution_line,
        build_distribution_load,
    )

    system, buses, _ = _minimal_time_series_system(SingleTimeSeries)
    secondary = build_distribution_buses()[7].model_copy(
        update={"rated_voltage": Voltage(0.4, "kilovolt")}
    )
    system.add_component(secondary)
    branch = build_distribution_line(buses[6], secondary)
    system.add_component(branch)
    inactive = build_distribution_load(secondary, 99)
    inactive.in_service = False
    system.add_component(inactive)

    reduced = reduce_to_minimal_system_with_sw(
        system, retain_out_of_service=True, reduce_series_laterals=True
    )

    for component in (inactive, secondary, buses[6], branch):
        assert reduced.has_component(component)
    assert reduced.has_component(system.get_component(DistributionTransformer, "substation_xfmr"))
    assert nx.has_path(reduced.get_undirected_graph(), buses[0].name, secondary.name)


def test_minimal_retains_isolated_out_of_service_bus():
    from tests.conftest import build_distribution_buses

    system, _, _ = _minimal_time_series_system(SingleTimeSeries)
    isolated = build_distribution_buses()[7]
    isolated.in_service = False
    system.add_component(isolated)

    reduced = reduce_to_minimal_system_with_sw(system, retain_out_of_service=True)

    assert reduced.has_component(isolated)
    assert not reduced.get_component(DistributionBus, isolated.name).in_service


def test_minimal_retains_secondary_outage_behind_open_switch():
    from tests.conftest import build_distribution_load

    system, buses, _ = _minimal_time_series_system(SingleTimeSeries)
    switch = next(system.get_components(MatrixImpedanceSwitch))
    switch.is_closed = [False] * 3
    transformer = system.get_component(DistributionTransformer, "substation_xfmr")
    system.remove_component(transformer, cascade_down=False)
    transformer = transformer.model_copy(update={"buses": [buses[4], buses[6]]})
    system.add_component(transformer)
    inactive = build_distribution_load(buses[6], 99)
    inactive.in_service = False
    system.add_component(inactive)

    reduced = reduce_to_minimal_system_with_sw(
        system, retain_out_of_service=True, reduce_series_laterals=True
    )

    for component in (switch, transformer, buses[4], buses[6], inactive):
        assert reduced.has_component(component)
    assert reduced.get_component(MatrixImpedanceSwitch, switch.name).is_closed == [False] * 3


def test_minimal_retention_option_preserves_results_without_outages():
    system, _, _ = _minimal_time_series_system(SingleTimeSeries)
    default = reduce_to_minimal_system_with_sw(system, reduce_series_laterals=True)
    retained = reduce_to_minimal_system_with_sw(
        system, reduce_series_laterals=True, retain_out_of_service=True
    )
    assert {bus.name for bus in retained.get_components(DistributionBus)} == {
        bus.name for bus in default.get_components(DistributionBus)
    }
    assert sum(
        get_total_kw(load) for load in retained.get_components(DistributionLoad)
    ) == pytest.approx(
        sum(get_total_kw(load) for load in default.get_components(DistributionLoad))
    )


@pytest.mark.parametrize("time_series_type", [SingleTimeSeries, NonSequentialTimeSeries])
@pytest.mark.parametrize("options", [{"agg_time_series": True}, {"agg_timeseries": True}])
def test_minimal_reduction_aggregates_time_series_across_all_stages(time_series_type, options):
    system, buses, _ = _minimal_time_series_system(time_series_type)
    reduced = reduce_to_minimal_system_with_sw(
        system, reduce_series_laterals=True, time_series_type=time_series_type, **options
    )

    loads = list(reduced.get_components(DistributionLoad))
    assert {load.bus.name for load in loads} == {buses[0].name}
    profiles = [
        reduced.get_time_series(
            load,
            "active_power",
            time_series_type=time_series_type,
            profile_type="PMult",
            profile_name="profile",
            use_actual=True,
        )
        .data.to("kilowatt")
        .magnitude
        for load in loads
    ]
    assert sum(profiles) == pytest.approx([16, 20])
    assert {bus.name for bus in reduced.get_components(DistributionBus)} == {
        buses[0].name,
        buses[3].name,
        buses[4].name,
    }


def test_minimal_time_series_alias_overrides_flag():
    system, _, _ = _minimal_time_series_system(SingleTimeSeries)
    reduced = reduce_to_minimal_system_with_sw(system, agg_time_series=True, agg_timeseries=False)
    assert all(
        not reduced.has_time_series(load) for load in reduced.get_components(DistributionLoad)
    )


def test_minimal_reduction_aggregates_multiplier_profiles_across_stages():
    system, _, _ = _minimal_time_series_system(SingleTimeSeries, multipliers=True)
    reduced = reduce_to_minimal_system_with_sw(
        system, reduce_series_laterals=True, agg_time_series=True
    )
    profiles = []
    for load in reduced.get_components(DistributionLoad):
        metadata = reduced.list_time_series_metadata(load)[0]
        profile = get_aggregated_load_time_series(
            reduced, [load], metadata.name, **metadata.features
        )
        profiles.append(profile.data.to("kilowatt").magnitude)
    assert sum(profiles) == pytest.approx([24, 48])


def test_minimal_reduction_preserves_distinct_profiles_for_same_variable():
    system, _, loads = _minimal_time_series_system(SingleTimeSeries)
    profile = SingleTimeSeries.from_array(
        data=ureg.Quantity([0.5, 1], "dimensionless"),
        name="active_power",
        initial_timestamp=datetime(2020, 1, 1),
        resolution=timedelta(hours=1),
    )
    system.add_time_series(
        profile, *loads.values(), profile_type="PMult", profile_name="multiplier", use_actual=False
    )
    reduced = reduce_to_minimal_system_with_sw(
        system, reduce_series_laterals=True, agg_time_series=True
    )
    results = {}
    for load in reduced.get_components(DistributionLoad):
        for metadata in reduced.list_time_series_metadata(load):
            profile = get_aggregated_load_time_series(
                reduced, [load], metadata.name, **metadata.features
            )
            name = metadata.features["profile_name"]
            results.setdefault(name, []).append(profile.data.to("kilowatt").magnitude)
    assert sum(results["profile"]) == pytest.approx([16, 20])
    assert sum(results["multiplier"]) == pytest.approx([24, 48])


def test_minimal_reduction_rejects_different_nonsequential_timestamps():
    system, _, _ = _minimal_time_series_system(NonSequentialTimeSeries, mismatched_timestamps=True)
    with pytest.raises(ValueError, match="different timestamps"):
        reduce_to_minimal_system_with_sw(
            system,
            reduce_series_laterals=True,
            agg_time_series=True,
            time_series_type=NonSequentialTimeSeries,
        )


def test_minimal_reduction_rejects_removed_branch_with_time_series():
    system, _, _ = _minimal_time_series_system(SingleTimeSeries)
    branch = system.get_component(MatrixImpedanceBranch, "line_bus_2_bus_5")
    profile = SingleTimeSeries.from_array(
        data=ActivePower([1, 2], "kilowatt"),
        name="active_power",
        initial_timestamp=datetime(2020, 1, 1),
        resolution=timedelta(hours=1),
    )
    system.add_time_series(profile, branch, profile_type="PMult", profile_name="branch")
    with pytest.raises(ValueError, match="Cannot remove MatrixImpedanceBranch.line_bus_2_bus_5"):
        reduce_to_minimal_system_with_sw(system, agg_time_series=True)
    assert system.has_time_series(branch)


def test_minimal_reduction_aggregates_solar_profiles_across_stages():
    from tests.conftest import build_distribution_solar

    system, buses, _ = _minimal_time_series_system(SingleTimeSeries)
    profile = SingleTimeSeries.from_array(
        data=Irradiance([0.5, 1], "kilowatt / meter ** 2"),
        name="irradiance",
        initial_timestamp=datetime(2020, 1, 1),
        resolution=timedelta(hours=1),
    )
    for index in (1, 5, 6):
        solar = build_distribution_solar(buses[index], index)
        system.add_component(solar)
        system.add_time_series(
            profile, solar, profile_type="PMult", profile_name="solar", use_actual=False
        )
    reduced = reduce_to_minimal_system_with_sw(
        system, reduce_series_laterals=True, agg_time_series=True
    )
    solar = next(reduced.get_components(DistributionSolar))
    result = reduced.get_time_series(
        solar, "irradiance", profile_type="PMult", profile_name="solar", use_actual=True
    )
    assert result.data.to("kilowatt").magnitude == pytest.approx([1.5015, 3.003])


def test_minimal_reduction_reports_unsupported_generator_profiles():
    system, buses, _ = _minimal_time_series_system(SingleTimeSeries)
    generator = DistributionGenerator.example().model_copy(
        update={"uuid": uuid4(), "name": "profiled_generator", "bus": buses[5]}
    )
    system.add_component(generator)
    profile = SingleTimeSeries.from_array(
        data=ActivePower([1, 2], "kilowatt"),
        name="active_power",
        initial_timestamp=datetime(2020, 1, 1),
        resolution=timedelta(hours=1),
    )
    system.add_time_series(
        profile, generator, profile_type="PMult", profile_name="profile", use_actual=True
    )
    with pytest.raises(ValueError, match="unsupported for DistributionGenerator"):
        reduce_to_minimal_system_with_sw(system, agg_time_series=True)


@pytest.mark.parametrize("stage", ["primary", "minimal", "series"])
def test_minimal_reduction_rejects_mismatched_time_series(stage):
    from tests.conftest import build_distribution_load

    system, buses, _ = _minimal_time_series_system(SingleTimeSeries)
    bus_index = {"primary": 6, "minimal": 5, "series": 1}[stage]
    system.add_component(build_distribution_load(buses[bus_index], 99))
    with pytest.raises(ValueError, match="mismatched DistributionLoad time series"):
        reduce_to_minimal_system_with_sw(system, reduce_series_laterals=True, agg_time_series=True)


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


def test_radial_reduction_opens_every_parallel_switch_conductor(simple_distribution_system):
    system = simple_distribution_system.deepcopy()
    system.auto_add_composed_components = True
    _add_loop_switch(system, "bus_0", "bus_4", "parallel_switch")
    original = system.get_component(MatrixImpedanceSwitch, "parallel_switch")
    switch = MatrixImpedanceSwitch(
        **(
            dict(original)
            | {"phases": [Phase.B, Phase.C], "conductor_phases": [Phase.B, Phase.B, Phase.C]}
        )
    )
    system.remove_component(original)
    system.add_component(switch)

    radial = reduce_to_radial_network(system, name="radial_system")
    opened = radial.get_component(MatrixImpedanceSwitch, "parallel_switch")
    assert opened.is_closed == [False, False, False]
    assert opened.conductor_phases == [Phase.B, Phase.B, Phase.C]
    assert switch.is_closed == [True, True, True]


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


@pytest.mark.parametrize("reducer", [reduce_to_primary_system, reduce_to_three_phase_system])
def test_reduction_excludes_inactive_load_from_aggregate_and_time_series(
    distribution_system_with_single_time_series, monkeypatch, reducer
):
    from gdm.systems.distribution.model_reduction import common

    system = distribution_system_with_single_time_series
    inactive = next(
        load for load in system.get_components(DistributionLoad) if Phase.S1 in load.phases
    )
    inactive.in_service = False
    expected_kw = sum(
        get_total_kw(load) for load in system.get_components(DistributionLoad) if load.in_service
    )
    aggregated_inputs = []
    original = common.get_aggregated_load_time_series

    def record_inputs(system, components, *args, **kwargs):
        aggregated_inputs.extend(components)
        return original(system, components, *args, **kwargs)

    monkeypatch.setattr(common, "get_aggregated_load_time_series", record_inputs)
    reduced = reducer(system, name="reduced", agg_time_series=True)

    assert sum(
        get_total_kw(load) for load in reduced.get_components(DistributionLoad)
    ) == pytest.approx(expected_kw)
    assert aggregated_inputs
    assert all(component.in_service for component in aggregated_inputs)
    assert inactive not in aggregated_inputs


@pytest.mark.parametrize("reducer", [reduce_to_primary_system, reduce_to_three_phase_system])
def test_reduction_skips_aggregate_if_all_subtree_loads_are_inactive(
    distribution_system_with_single_time_series, reducer
):
    system = distribution_system_with_single_time_series
    for load in system.get_components(DistributionLoad):
        if Phase.S1 in load.phases or Phase.S2 in load.phases:
            load.in_service = False

    reduced = reducer(system, name="reduced", agg_time_series=True)

    expected_kw = sum(
        get_total_kw(load) for load in system.get_components(DistributionLoad) if load.in_service
    )
    assert sum(
        get_total_kw(load) for load in reduced.get_components(DistributionLoad)
    ) == pytest.approx(expected_kw)


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


def test_three_phase_reduction_groups_compatible_generators():
    system, buses = _build_phase_split_system()
    example = DistributionGenerator.example()
    for name, mode, in_service in (
        ("first", GeneratorOperatingMode.CONSTANT_PQ, True),
        ("second", GeneratorOperatingMode.CONSTANT_PQ, True),
        ("different", GeneratorOperatingMode.CONSTANT_PV, True),
        ("outage", GeneratorOperatingMode.CONSTANT_PQ, False),
    ):
        system.add_component(
            example.model_copy(
                update={
                    "uuid": uuid4(),
                    "name": name,
                    "bus": buses["lat_bus"],
                    "phases": [Phase.A],
                    "operating_mode": mode,
                    "in_service": in_service,
                }
            )
        )

    reduced = reduce_to_three_phase_system(system, "reduced", include_intermediate_buses=True)
    generators = list(reduced.get_components(DistributionGenerator))
    assert len(generators) == 2
    by_mode = {generator.operating_mode: generator for generator in generators}
    assert by_mode[GeneratorOperatingMode.CONSTANT_PQ].active_power.to("kW").magnitude == 1000
    assert by_mode[GeneratorOperatingMode.CONSTANT_PV].active_power.to("kW").magnitude == 500
    assert all(generator.bus.name == "bus_X" for generator in generators)
    assert len(list(system.get_components(DistributionGenerator))) == 4


def test_primary_reduction_reports_unsupported_generator_profiles(simple_distribution_system):
    system = simple_distribution_system
    generator = DistributionGenerator.example().model_copy(
        update={
            "uuid": uuid4(),
            "name": "profiled_generator",
            "bus": system.get_component(DistributionBus, "bus_5"),
        }
    )
    system.add_component(generator)
    profile = SingleTimeSeries.from_array(
        data=ActivePower([1, 2], "kilowatt"),
        name="active_power",
        initial_timestamp=datetime(2020, 1, 1),
        resolution=timedelta(minutes=30),
    )
    system.add_time_series(
        profile, generator, profile_type="PMult", profile_name="profile", use_actual=True
    )
    with pytest.raises(ValueError, match="unsupported for DistributionGenerator"):
        reduce_to_primary_system(system, "reduced", agg_time_series=True)


def test_primary_reduction_aggregates_split_phase_generators(simple_distribution_system):
    system = simple_distribution_system
    example = DistributionGenerator.example()
    for name in ("first", "second"):
        system.add_component(
            example.model_copy(
                update={
                    "uuid": uuid4(),
                    "name": name,
                    "bus": system.get_component(DistributionBus, "split_phase_bus_9"),
                    "phases": [Phase.S1, Phase.S2],
                }
            )
        )
    reduced = reduce_to_primary_system(system, "reduced")
    generator = next(reduced.get_components(DistributionGenerator))
    assert generator.active_power.to("kW").magnitude == 1000
    assert set(generator.phases) == {Phase.A, Phase.B, Phase.C}
    assert generator.bus.name == "src_bus"


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


def test_reduce_to_radial_converts_shortest_line(simple_distribution_system, tmp_path):
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
    assert switch.equipment.uuid != original_line.equipment.uuid
    assert reduced.get_component_by_uuid(switch.equipment.uuid) is switch.equipment
    reduced_again = reduce_to_radial_network(system, name="radial_system")
    assert (
        reduced_again.get_component(MatrixImpedanceSwitch, switch.name).equipment.uuid
        == switch.equipment.uuid
    )

    reloaded = _export_and_reload(reduced, tmp_path)
    assert (
        reloaded.get_component(MatrixImpedanceSwitch, switch.name).equipment.uuid
        == switch.equipment.uuid
    )

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
