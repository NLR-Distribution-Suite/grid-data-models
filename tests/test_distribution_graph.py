from io import StringIO

from loguru import logger
import networkx as nx
import pytest
from uuid import uuid4

from gdm.distribution.components import (
    DistributionLoad,
    DistributionBus,
    MatrixImpedanceSwitch,
    MatrixImpedanceBranch,
)
from gdm.exceptions import NonuniqueCommponentsTypesInParallel
from gdm.distribution import DistributionSystem

from .get_sample_system import get_three_bus_system


@pytest.fixture
def distribution_system():
    """Creates a dummy system."""
    sys = get_three_bus_system()
    yield sys


def test_distribution_graph(distribution_system: DistributionSystem):
    """Tests distribution graph."""
    graph_instance = distribution_system.get_undirected_graph()
    assert isinstance(graph_instance, nx.MultiGraph)
    assert isinstance(
        distribution_system.get_bus_connected_components("Bus-3", DistributionLoad)[0],
        DistributionLoad,
    )


def test_distribution_graph_multiple_edges_different_types(
    simple_distribution_system: DistributionSystem,
):
    """Tests distribution graph."""
    system = simple_distribution_system.deepcopy()
    system.auto_add_composed_components = True

    branch = next(system.get_components(MatrixImpedanceBranch))
    switch = MatrixImpedanceSwitch.example()
    switch.buses = branch.buses
    switch.is_closed = [False, False, False]

    switch_copy = switch.model_copy(update={"uuid": uuid4()})
    system.add_component(switch_copy)

    graph_instance = system.get_undirected_graph()

    with pytest.raises(NonuniqueCommponentsTypesInParallel):
        system.get_cycles(graph_instance)


def test_distribution_graph_multiple_edges(simple_distribution_system: DistributionSystem):
    """Tests distribution graph."""
    system = simple_distribution_system.deepcopy()
    system.auto_add_composed_components = True

    buses = sorted(system.get_components(DistributionBus), key=lambda x: x.name)
    switch = MatrixImpedanceSwitch.example()
    switch.buses = [buses[0], buses[4]]
    switch.is_closed = [False, False, False]

    for _ in range(2):
        switch_copy = switch.model_copy(update={"uuid": uuid4()})
        system.add_component(switch_copy)

    graph_instance = system.get_undirected_graph()
    assert isinstance(graph_instance, nx.MultiGraph)
    assert graph_instance.number_of_nodes() == 21
    assert graph_instance.number_of_edges() == 22
    cycles = system.get_cycles(graph_instance)
    assert len(cycles) == 1


def test_get_cycles_keeps_two_node_directed_cycle():
    graph = nx.MultiDiGraph()
    graph.add_edge("bus-a", "bus-b", name="forward", type=MatrixImpedanceSwitch)
    graph.add_edge("bus-b", "bus-a", name="reverse", type=MatrixImpedanceSwitch)

    assert len(DistributionSystem.get_cycles(graph)) == 1


def test_distribution_graph_directed_open_switch(
    simple_distribution_system: DistributionSystem,
):
    """Tests distribution graph."""

    system = simple_distribution_system.deepcopy()
    system.auto_add_composed_components = True

    buses = sorted(system.get_components(DistributionBus), key=lambda x: x.name)
    switch = MatrixImpedanceSwitch.example()
    switch.buses = [buses[0], buses[4]]
    switch.is_closed = [False, False, False]
    system.add_component(switch)

    graph_instance = system.get_directed_graph(False)
    assert graph_instance.number_of_nodes() == 21
    assert graph_instance.number_of_edges() == 21
    assert graph_instance.has_edge(switch.buses[0].name, switch.buses[1].name)

    log_stream = StringIO()
    logger.add(log_stream, level="WARNING")

    graph_instance = system.get_directed_graph(True)
    assert graph_instance.number_of_nodes() == 21
    assert graph_instance.number_of_edges() == 20
    assert not graph_instance.has_edge(switch.buses[0].name, switch.buses[1].name)

    log_contents = log_stream.getvalue()
    assert "| WARNING  |" not in log_contents


def test_distribution_graph_directed_closed_switch(
    simple_distribution_system: DistributionSystem,
):
    """Tests distribution graph."""

    system = simple_distribution_system.deepcopy()
    system.auto_add_composed_components = True

    buses = sorted(system.get_components(DistributionBus), key=lambda x: x.name)
    switch = MatrixImpedanceSwitch.example()
    switch.buses = [buses[0], buses[4]]
    switch.is_closed = [True, True, True]
    switch_copy = switch.model_copy(update={"uuid": uuid4(), "name": "test_switch_123"})
    system.add_component(switch_copy)

    assert system.has_component(switch_copy)

    graph_instance = system.get_directed_graph(False)

    assert graph_instance.number_of_nodes() == 21
    assert graph_instance.number_of_edges() == 21
    assert graph_instance.has_edge(
        switch.buses[0].name, switch.buses[1].name
    ) or graph_instance.has_edge(switch.buses[1].name, switch.buses[0].name)

    log_stream = StringIO()
    logger.add(log_stream, level="WARNING")

    graph_instance = system.get_directed_graph(True)

    assert graph_instance.number_of_nodes() == 21
    assert graph_instance.number_of_edges() == 20

    log_contents = log_stream.getvalue()
    assert "| WARNING  |" in log_contents


def test_directed_graph_multiple_loops_pruning(simple_distribution_system: DistributionSystem):
    """Ensure get_directed_graph prunes cycles to a radial tree when requested."""

    system = simple_distribution_system.deepcopy()
    system.auto_add_composed_components = True

    buses = sorted(system.get_components(DistributionBus), key=lambda x: x.name)

    # Add two additional switches creating multiple loops in the network
    sw1 = MatrixImpedanceSwitch.example()
    sw1.buses = [buses[0], buses[4]]
    sw1.is_closed = [True, True, True]
    system.add_component(sw1.model_copy(update={"uuid": sw1.uuid, "name": "test_switch_1"}))

    sw2 = MatrixImpedanceSwitch.example()
    sw2.buses = [buses[1], buses[5]]
    sw2.is_closed = [True, True, True]
    system.add_component(sw2.model_copy(update={"uuid": sw2.uuid, "name": "test_switch_2"}))

    radial = system.get_directed_graph(return_radial_network=True)

    assert radial.number_of_nodes() == system.get_undirected_graph().number_of_nodes()
    assert radial.number_of_edges() == radial.number_of_nodes() - 1

    # When not requesting a radial network, pruned edges are kept
    full = system.get_directed_graph(return_radial_network=False)
    assert full.number_of_edges() >= radial.number_of_edges()
