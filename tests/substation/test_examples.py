"""Tests for the executable substation layout examples."""

from collections import Counter

import pytest

from gdm.systems.substation import (
    Bay,
    BusbarSection,
    CircuitBreaker,
    Disconnector,
    FeederBoundary,
    PowerTransformer,
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
from tests.substation.detailed_example import build_detailed_distribution_substation


def _physical_buses(system):
    """Return busbar sections that are physical busbars rather than junctions."""

    return [bus for bus in system.get_components(BusbarSection) if bus.length is not None]


def _equipment_buses(system):
    for component in system.iter_all_components():
        buses = getattr(component, "buses", None)
        if buses:
            yield component, buses


@pytest.mark.parametrize("layout", SubstationLayout)
def test_each_layout_builds_a_substation_system(layout):
    system = build_layout_example(layout)

    assert system.name == f"{layout.value.replace('_', '-')}-substation"
    assert len(_physical_buses(system)) >= 1
    assert len(list(system.get_components(Bay))) >= 1
    assert len(list(system.get_components(FeederBoundary))) >= 1


def test_layout_registry_covers_every_layout():
    assert set(LAYOUT_EXAMPLES) == set(SubstationLayout)


@pytest.mark.parametrize("layout", SubstationLayout)
def test_layout_cross_references_resolve(layout):
    system = build_layout_example(layout)
    names = {component.name for component in system.iter_all_components()}

    for component, buses in _equipment_buses(system):
        assert all(isinstance(bus, BusbarSection) for bus in buses)
        for bus in buses:
            assert bus.name in names
    for bay in system.get_components(Bay):
        assert bay.voltage_level is None or bay.voltage_level.name in names
    for boundary in system.get_components(FeederBoundary):
        assert isinstance(boundary.bus, BusbarSection)
        assert boundary.bay is None or boundary.bay.name in names


def test_single_bus_has_one_bus_and_three_feeders():
    system = build_layout_example("single_bus")

    assert len(_physical_buses(system)) == 1
    assert len(list(system.get_components(BusbarSection))) == 4
    assert len(list(system.get_components(CircuitBreaker))) == 3
    assert len(list(system.get_components(FeederBoundary))) == 3


def test_sectionalized_single_bus_has_normally_open_tie():
    system = build_layout_example(SubstationLayout.SECTIONALIZED_SINGLE_BUS)
    breakers = {breaker.name: breaker for breaker in system.get_components(CircuitBreaker)}

    assert len(_physical_buses(system)) == 2
    assert breakers["bus-tie-breaker"].state.value == "open"
    assert len(list(system.get_components(FeederBoundary))) == 4


def test_ring_bus_forms_a_closed_cycle_of_bus_nodes():
    system = build_layout_example(SubstationLayout.RING_BUS)
    ring_breakers = [
        breaker
        for breaker in system.get_components(CircuitBreaker)
        if breaker.name.startswith("ring-breaker")
    ]
    node_degrees = Counter(node.name for breaker in ring_breakers for node in breaker.buses)

    assert len(_physical_buses(system)) == 4
    assert len(ring_breakers) == 4
    assert len(list(system.get_components(FeederBoundary))) == 4
    assert set(node_degrees.values()) == {2}


def test_breaker_and_a_half_has_two_parallel_three_breaker_diameters():
    system = build_layout_example(SubstationLayout.BREAKER_AND_A_HALF)
    diameter_breakers = [
        breaker
        for breaker in system.get_components(CircuitBreaker)
        if breaker.bay and breaker.bay.name.startswith("diameter-")
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
    assert {bus.name for bus in transformer.buses} == {"hv-bus", "mv-bus"}
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


@pytest.mark.parametrize("layout", SubstationLayout)
def test_connectivity_graph_matches_bus_and_equipment_counts(layout):
    system = build_layout_example(layout)
    graph = system.get_undirected_graph()
    physical_buses = _physical_buses(system)

    assert set(graph.nodes()) == {bus.name for bus in system.get_components(BusbarSection)}
    assert all(graph.nodes[bus.name]["is_busbar"] for bus in physical_buses)


def test_sectionalized_tie_breaker_is_open_in_graph():
    system = build_layout_example(SubstationLayout.SECTIONALIZED_SINGLE_BUS)
    graph = system.get_undirected_graph()
    tie = next(data for _, _, data in graph.edges(data=True) if data["name"] == "bus-tie-breaker")

    assert tie["is_closed"] is False
    assert tie["state"] == "open"


def test_disconnectors_are_present_in_double_bus_layout():
    system = build_layout_example(SubstationLayout.DOUBLE_BUS_SINGLE_BREAKER)

    assert len(list(system.get_components(Disconnector))) == 4


def test_detailed_transformer_hv_path_reaches_the_winding():
    system = build_detailed_distribution_substation()
    graph = system.get_undirected_graph()

    for number in (1, 2):
        hv_node = f"transformer-{number}-hv-node"
        winding_node = f"transformer-{number}-hv-winding-node"
        edge = graph.get_edge_data(hv_node, winding_node)

        assert edge is not None
        assert next(iter(edge.values()))["name"] == f"transformer-{number}-hv-ct"
