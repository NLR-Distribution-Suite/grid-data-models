"""Topology analysis tools for distribution systems."""

from typing import Optional

import networkx as nx
from gdm.systems.distribution import DistributionSystem
from gdm.exceptions import MultipleOrEmptyVsourceFound

from gdm.mcp.exceptions import TopologyError
from gdm.mcp.schemas import TopologyMetrics


def analyze_topology(system: DistributionSystem) -> TopologyMetrics:
    """
    Analyze the network topology of a distribution system.

    Args:
        system: DistributionSystem to analyze

    Returns:
        TopologyMetrics with graph statistics

    Raises:
        TopologyError: If topology analysis fails
    """
    try:
        # Get directed graph
        graph = system.get_directed_graph()

        # Basic metrics
        node_count = graph.number_of_nodes()
        edge_count = graph.number_of_edges()

        # Find source bus
        has_source = False
        source_bus_name: Optional[str] = None
        try:
            source_bus = system.get_source_bus()
            has_source = True
            source_bus_name = source_bus.name
        except MultipleOrEmptyVsourceFound:
            pass

        # Check for cycles (should be 0 for radial systems)
        undirected = system.get_undirected_graph()
        cycles = list(system.get_cycles(undirected))
        cycle_count = len(cycles)
        is_radial = cycle_count == 0

        # Find islands (disconnected components)
        if node_count > 0:
            connected_components = list(nx.weakly_connected_components(graph))
            island_count = len(connected_components)
        else:
            island_count = 0

        # Max degree (most connected node)
        if node_count > 0:
            max_degree = max(dict(graph.degree()).values())
        else:
            max_degree = 0

        return TopologyMetrics(
            node_count=node_count,
            edge_count=edge_count,
            has_source=has_source,
            source_bus_name=source_bus_name,
            cycle_count=cycle_count,
            island_count=island_count,
            is_radial=is_radial,
            max_degree=max_degree,
        )

    except Exception as e:
        raise TopologyError(f"Failed to analyze topology: {str(e)}") from e


def validate_connectivity(system: DistributionSystem) -> dict[str, any]:
    """
    Validate that all components are reachable from the source bus.

    Args:
        system: DistributionSystem to validate

    Returns:
        Dictionary with connectivity results:
            - is_connected: bool
            - source_bus: str or None
            - reachable_buses: list[str]
            - unreachable_buses: list[str]
            - island_count: int

    Raises:
        TopologyError: If validation fails
    """
    try:
        # Get source bus
        try:
            source_bus = system.get_source_bus()
            source_name = source_bus.name
        except MultipleOrEmptyVsourceFound as e:
            return {
                "is_connected": False,
                "source_bus": None,
                "reachable_buses": [],
                "unreachable_buses": [],
                "island_count": 0,
                "error": str(e),
            }

        # Get directed graph
        graph = system.get_directed_graph()

        # Find all buses reachable from source
        if source_name in graph:
            reachable = set(nx.descendants(graph, source_name))
            reachable.add(source_name)  # Include source itself
        else:
            reachable = set()

        # Get all buses in system
        all_buses = set(graph.nodes())

        # Find unreachable buses
        unreachable = all_buses - reachable

        # Count islands
        island_count = len(list(nx.weakly_connected_components(graph)))

        is_connected = len(unreachable) == 0

        return {
            "is_connected": is_connected,
            "source_bus": source_name,
            "reachable_buses": sorted(list(reachable)),
            "unreachable_buses": sorted(list(unreachable)),
            "island_count": island_count,
        }

    except Exception as e:
        raise TopologyError(f"Failed to validate connectivity: {str(e)}") from e
