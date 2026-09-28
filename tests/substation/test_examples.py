"""Tests for the executable substation layout examples."""

from collections import Counter

import pytest

from gdm.systems.substation import (
    Bay,
    BusbarSection,
    CircuitBreaker,
    FeederBoundary,
    PowerTransformer,
    Terminal,
    VoltageLevel,
)
from gdm.systems.distribution.components import (
    DistributionBus,
    DistributionFeeder,
    MatrixImpedanceBranch,
)
from tests.substation import (
    LAYOUT_EXAMPLES,
    SubstationLayout,
    build_layout_example,
    hv_mv_substation_with_distribution_feeders,
)


@pytest.mark.parametrize("layout", SubstationLayout)
def test_each_layout_builds_a_substation_system(layout):
    system = build_layout_example(layout)

    assert system.name == f"{layout.value.replace('_', '-')}-substation"
    assert len(list(system.get_components(BusbarSection))) >= 1
    assert len(list(system.get_components(Bay))) >= 1
    assert len(list(system.get_components(FeederBoundary))) >= 1


def test_layout_registry_covers_every_layout():
    assert set(LAYOUT_EXAMPLES) == set(SubstationLayout)


@pytest.mark.parametrize("layout", SubstationLayout)
def test_layout_cross_references_resolve(layout):
    system = build_layout_example(layout)
    names = {component.name for component in system.iter_all_components()}

    for bay in system.get_components(Bay):
        assert set(bay.equipment_ids) <= names
        assert set(bay.terminal_ids) <= names
    for boundary in system.get_components(FeederBoundary):
        assert boundary.bay_id in names
        assert boundary.terminal_id in names


def test_single_bus_has_one_bus_and_three_feeders():
    system = build_layout_example("single_bus")

    assert len(list(system.get_components(BusbarSection))) == 1
    assert len(list(system.get_components(CircuitBreaker))) == 3
    assert len(list(system.get_components(FeederBoundary))) == 3
    assert len(list(system.get_components(Terminal))) == 6


def test_sectionalized_single_bus_has_normally_open_tie():
    system = build_layout_example(SubstationLayout.SECTIONALIZED_SINGLE_BUS)
    breakers = {breaker.name: breaker for breaker in system.get_components(CircuitBreaker)}

    assert len(list(system.get_components(BusbarSection))) == 2
    assert breakers["bus-tie-breaker"].state.value == "open"
    assert len(list(system.get_components(FeederBoundary))) == 4


def test_ring_bus_forms_a_closed_cycle_of_bus_nodes():
    system = build_layout_example(SubstationLayout.RING_BUS)
    ring_breakers = list(system.get_components(CircuitBreaker))
    terminals = list(system.get_components(Terminal))
    endpoints = {
        frozenset(
            terminal.connectivity_node_id
            for terminal in terminals
            if terminal.equipment_id == breaker.name
        )
        for breaker in ring_breakers
    }
    node_degrees = Counter(node for edge in endpoints for node in edge)

    assert len(list(system.get_components(BusbarSection))) == 4
    assert len(ring_breakers) == 4
    assert len(list(system.get_components(FeederBoundary))) == 4
    assert len(endpoints) == 4
    assert set(node_degrees.values()) == {2}


def test_breaker_and_a_half_has_two_parallel_three_breaker_diameters():
    system = build_layout_example(SubstationLayout.BREAKER_AND_A_HALF)
    diameter_breakers = [
        breaker
        for breaker in system.get_components(CircuitBreaker)
        if breaker.bay_id and breaker.bay_id.startswith("diameter-")
    ]

    assert len(diameter_breakers) == 6
    assert len(list(system.get_components(FeederBoundary))) == 4


def test_hv_mv_example_has_buses_and_station_transformer_between_them():
    system = build_layout_example(SubstationLayout.HV_MV_SINGLE_BUS)
    voltage_levels = {level.name: level for level in system.get_components(VoltageLevel)}
    transformer = next(system.get_components(PowerTransformer))

    assert set(voltage_levels) == {"voltage-level-hv", "voltage-level-mv"}
    assert {level.nominal_voltage.magnitude for level in voltage_levels.values()} == {12.47, 69}
    assert {winding.rated_voltage.magnitude for winding in transformer.equipment.windings} == {
        12.47,
        69,
    }
    assert {
        terminal.connectivity_node_id
        for terminal in system.get_components(Terminal)
        if terminal.equipment_id == transformer.name
    } == {"hv-bus-node", "mv-bus-node"}
    assert len(list(system.get_components(FeederBoundary))) == 3


def test_hv_mv_example_links_to_real_distribution_feeder_system():
    substation_system, distribution_system = hv_mv_substation_with_distribution_feeders()
    boundaries = list(substation_system.get_components(FeederBoundary))
    feeder_names = {
        feeder.name for feeder in distribution_system.get_components(DistributionFeeder)
    }

    assert distribution_system.name == "hv-mv-distribution-feeders"
    assert {boundary.feeder_id for boundary in boundaries} == feeder_names
    assert {boundary.distribution_model_reference_id for boundary in boundaries} == {
        distribution_system.name
    }
    assert len(list(distribution_system.get_components(DistributionBus))) == 6
    assert len(list(distribution_system.get_components(MatrixImpedanceBranch))) == 3
    assert len(distribution_system.to_gdf()) == 9


@pytest.mark.parametrize("layout", SubstationLayout)
def test_layout_round_trips_with_stable_component_names(tmp_path, layout):
    system = build_layout_example(layout)
    filename = tmp_path / f"{layout.value}.json"

    system.to_json(filename, overwrite=True)
    restored = type(system).from_json(filename)

    assert Counter(
        type(component).__name__ for component in restored.iter_all_components()
    ) == Counter(type(component).__name__ for component in system.iter_all_components())
    assert {component.name for component in restored.iter_all_components()} == {
        component.name for component in system.iter_all_components()
    }
