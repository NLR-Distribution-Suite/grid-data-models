"""This module contains class for creating graph representation of Distribution System."""

import warnings

import networkx as nx
from infrasys import System

from gdm.systems.distribution.components import (
    DistributionTransformerBase,
    DistributionBranchBase,
    DistributionBus,
)


def build_graph_from_system(system: System) -> nx.Graph:
    """Returns networkx instance of the system."""

    warnings.warn(
        """This function will be deprecated in future version (after v2.0.0)
        You can use `system.get_undirected_graph()` instead.
        """,
        DeprecationWarning,
        stacklevel=2,
    )

    graph = nx.Graph()
    node: DistributionBus
    for node in system.get_components(DistributionBus):
        graph.add_node(node.name)

    edges: list[DistributionBranchBase | DistributionTransformerBase] = list(
        system.get_components(DistributionBranchBase)
    ) + list(system.get_components(DistributionTransformerBase))

    for edge in edges:
        graph.add_edge(
            edge.buses[0].name,
            edge.buses[1].name,
            **{"name": edge.name, "type": edge.__class__},
        )
    return graph
