"""Tests for the public substation builder and the detailed reference design."""

from collections import Counter

from gdm.systems.substation import (
    InstrumentTransformer,
    MeteringPoint,
    ProtectionFunction,
    ProtectionIED,
    SubstationSystem,
)
from gdm.systems.substation.automation import ProtocolEndpoint, SemanticSignal
from gdm.systems.substation.components import CircuitBreaker
from gdm.systems.substation.topology import BusbarSection, FeederBoundary, VoltageLevel
from gdm.systems.substation.builder import SubstationBuilder
from gdm.systems.substation.detailed_reference import build_detailed_distribution_substation


def _physical_buses(system):
    return [bus for bus in system.get_components(BusbarSection) if bus.length is not None]


def test_builder_assembles_a_basic_station():
    builder = SubstationBuilder("test-station")
    builder.add_bus("bus-a")
    _, breaker_to = builder.add_breaker("feeder-breaker", "feeder-bay", "bus-a", "feeder-node")
    builder.add_feeder("feeder-1", "feeder-bay", "feeder-node", bus=breaker_to)
    system = builder.build()

    assert isinstance(system, SubstationSystem)
    assert system.name == "test-station"
    assert len(list(system.get_components(CircuitBreaker))) == 1
    assert len(list(system.get_components(FeederBoundary))) == 1
    assert len(list(system.get_components(BusbarSection))) == 2


def test_builder_reuses_shared_references():
    builder = SubstationBuilder("refs")
    builder.add_bus("bus-a")
    builder.add_breaker("b1", "bay-1", "bus-a", "n1")
    builder.add_breaker("b2", "bay-2", "bus-a", "n2")
    system = builder.build()
    bus = system.get_component(BusbarSection, "bus-a")

    for breaker in system.get_components(CircuitBreaker):
        assert any(node.name == bus.name for node in breaker.buses)


def test_detailed_distribution_substation_is_complete():
    system = build_detailed_distribution_substation()

    assert len(_physical_buses(system)) == 4
    assert len(list(system.get_components(VoltageLevel))) == 2
    assert len(list(system.get_components(CircuitBreaker))) == 12
    assert len(list(system.get_components(InstrumentTransformer))) == 10
    assert len(list(system.get_components(FeederBoundary))) == 4
    assert len(list(system.get_components(ProtectionFunction))) == 8
    assert len(list(system.get_components(ProtectionIED))) == 8
    assert len(list(system.get_components(MeteringPoint))) == 4
    assert len(list(system.get_components(ProtocolEndpoint))) == 1
    assert len(list(system.get_components(SemanticSignal))) == 12


def test_detailed_distribution_substation_round_trips(tmp_path):
    system = build_detailed_distribution_substation()
    filename = tmp_path / "detailed.json"

    system.to_json(filename, overwrite=True)
    restored = SubstationSystem.from_json(filename)

    assert Counter(
        type(component).__name__ for component in restored.iter_all_components()
    ) == Counter(type(component).__name__ for component in system.iter_all_components())


def test_detailed_distribution_substation_graph_connects_buses():
    system = build_detailed_distribution_substation()
    graph = system.get_undirected_graph()

    assert set(graph.nodes()) == {bus.name for bus in system.get_components(BusbarSection)}
    assert graph.number_of_edges() >= 12
    assert any(not data["is_closed"] for _, _, data in graph.edges(data=True))


def test_referenced_equipment_resolves():
    system = build_detailed_distribution_substation()
    feeder_ct = system.get_component(InstrumentTransformer, "feeder-1-ct")

    assert len(feeder_ct.cores) == 2
    assert {core.core_type for core in feeder_ct.cores} == {"protection", "metering"}
    for core in feeder_ct.cores:
        assert system.has_component(core)
