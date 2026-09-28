"""Substation facility and electrical topology models."""

import math
from pathlib import Path
from typing import Annotated

import networkx as nx
import plotly.graph_objects as go
from pydantic import Field, model_validator
from infrasys import Component, System
from loguru import logger

from gdm.quantities import Distance, Voltage
from gdm.constants import PINT_SCHEMA
from gdm.systems.distribution.enums import Phase, VoltageTypes
from gdm.systems.substation.enums import (
    CircuitDirection,
    EquipmentState,
    LifecycleStatus,
    SubstationType,
    TerminalRole,
)
from gdm.systems.substation.components import EarthingSwitch, PrimaryEquipmentComponent
from gdm.systems.substation.models import (
    AssetReference,
    DocumentReference,
    ExternalIdentifier,
    LifecycleRecord,
    ModelReference,
    Rating,
    StandardProfile,
    StateObservation,
)


class VoltageLevel(Component):
    """Nominal voltage grouping within a substation."""

    nominal_voltage: Annotated[Voltage, PINT_SCHEMA, Field(..., gt=0)]
    voltage_type: VoltageTypes
    frequency_hz: float = Field(60, gt=0)
    phases: list[Phase] = Field(default_factory=lambda: [Phase.A, Phase.B, Phase.C])
    standard_profile_id: str | None = None

    @classmethod
    def example(cls) -> "VoltageLevel":
        return cls(
            name="medium-voltage",
            nominal_voltage=Voltage(12.47, "kilovolt"),
            voltage_type=VoltageTypes.LINE_TO_LINE,
        )


class ConnectivityNode(Component):
    """Physical electrical junction independent of switch state."""

    voltage_level_id: str
    phases: list[Phase]
    state_observations: list[StateObservation] = Field(default_factory=list)

    @classmethod
    def example(cls) -> "ConnectivityNode":
        return cls(
            name="mv-bus-node",
            voltage_level_id="voltage-level-mv",
            phases=[Phase.A, Phase.B, Phase.C],
        )


class TopologicalNode(Component):
    """State-dependent calculated node derived from connectivity nodes."""

    connectivity_node_ids: list[str]
    topology_state_id: str
    voltage_level_id: str

    @classmethod
    def example(cls) -> "TopologicalNode":
        return cls(
            name="mv-topological-node",
            connectivity_node_ids=["mv-bus-node"],
            topology_state_id="normal-state",
            voltage_level_id="voltage-level-mv",
        )


class Terminal(Component):
    """Electrical endpoint of primary equipment."""

    connectivity_node_id: str
    phases: list[Phase]
    role: TerminalRole = TerminalRole.OTHER
    equipment_id: str
    diagram_position: tuple[float, float] | None = None

    @classmethod
    def example(cls) -> "Terminal":
        return cls(
            name="feeder-breaker-feeder-terminal",
            connectivity_node_id="mv-bus-node",
            phases=[Phase.A, Phase.B, Phase.C],
            role=TerminalRole.FEEDER_SIDE,
            equipment_id="feeder-breaker-001",
            diagram_position=(0, 0),
        )


class Bay(Component):
    """Functional station equipment grouping."""

    voltage_level_id: str
    equipment_ids: list[str] = Field(default_factory=list)
    terminal_ids: list[str] = Field(default_factory=list)
    protection_scheme_ids: list[str] = Field(default_factory=list)
    ied_ids: list[str] = Field(default_factory=list)

    @classmethod
    def example(cls) -> "Bay":
        return cls(name="feeder-bay-001", voltage_level_id="voltage-level-mv")


class BusbarSection(Component):
    """Physical busbar section within a voltage level."""

    voltage_level_id: str
    connectivity_node_id: str
    phases: list[Phase]
    state: EquipmentState = EquipmentState.CLOSED
    length: Annotated[Distance | None, PINT_SCHEMA, Field(None, gt=0)]
    diagram_start: tuple[float, float] | None = None
    diagram_end: tuple[float, float] | None = None

    @model_validator(mode="after")
    def validate_diagram_segment(self) -> "BusbarSection":
        if (self.diagram_start is None) != (self.diagram_end is None):
            raise ValueError("BusbarSection requires both diagram_start and diagram_end.")
        if self.diagram_start == self.diagram_end and self.diagram_start is not None:
            raise ValueError("BusbarSection diagram endpoints must be distinct.")
        return self

    @classmethod
    def example(cls) -> "BusbarSection":
        return cls(
            name="mv-bus-section-1",
            voltage_level_id="voltage-level-mv",
            connectivity_node_id="mv-bus-node",
            phases=[Phase.A, Phase.B, Phase.C],
            length=Distance(12, "meter"),
            diagram_start=(-3, 0),
            diagram_end=(3, 0),
        )


class FeederBoundary(Component):
    """Contract between a substation station model and a distribution model."""

    feeder_id: str
    substation_id: str
    voltage_level_id: str
    bay_id: str
    terminal_id: str
    distribution_model_reference_id: str | None = None
    source_equivalent_id: str | None = None

    @classmethod
    def example(cls) -> "FeederBoundary":
        return cls(
            name="feeder-boundary-001",
            feeder_id="feeder-001",
            substation_id="substation-001",
            voltage_level_id="voltage-level-mv",
            bay_id="feeder-bay-001",
            terminal_id="feeder-breaker-feeder-terminal",
        )


class ExternalCircuit(Component):
    """Incoming or outgoing transmission, subtransmission, or distribution circuit."""

    circuit_id: str
    terminal_id: str
    direction: CircuitDirection
    voltage_level_id: str
    bay_id: str | None = None

    @classmethod
    def example(cls) -> "ExternalCircuit":
        return cls(
            name="incoming-line-001",
            circuit_id="incoming-line-001",
            terminal_id="incoming-line-terminal",
            direction=CircuitDirection.INCOMING,
            voltage_level_id="voltage-level-hv",
            bay_id="incoming-line-bay-001",
        )


class DiagramPosition(Component):
    """Author-specified schematic coordinate for a station object."""

    target_id: str
    x: float
    y: float

    @classmethod
    def example(cls) -> "DiagramPosition":
        return cls(name="main-bus-position", target_id="main-bus-node", x=0, y=0)


class SubstationSystem(System):
    """Utility substation design and station-automation system."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.data_format_version:
            from importlib.metadata import version

            self.data_format_version = version("grid-data-models")

    def plot(
        self,
        export_path: Path | str | None = None,
        show: bool = True,
        show_legend: bool = True,
        **kwargs,
    ) -> go.Figure:
        """Create an interactive schematic of the station electrical topology.

        Parameters
        ----------
        export_path : Path | str | None
            Existing directory in which to write ``<system-name>_plot.html``.
        show : bool
            If True, display the Plotly figure in a browser or notebook.
        show_legend : bool
            If True, display the schematic legend.
        **kwargs
            Additional Plotly layout options, such as ``width`` or ``height``.

        Returns
        -------
        plotly.graph_objects.Figure
            The generated interactive schematic.

        Raises
        ------
        NotADirectoryError
            If ``export_path`` points to an existing file.
        FileNotFoundError
            If ``export_path`` does not exist.
        """

        graph = self._build_plot_graph()
        positions = self._build_plot_positions(graph)
        figure = go.Figure()

        self._add_plot_busbar_traces(figure, graph)
        self._add_plot_edge_trace(figure, graph, positions)
        self._add_plot_node_traces(figure, graph, positions)

        layout_options = {
            "title": self.name,
            "showlegend": show_legend,
            "hovermode": "closest",
            "template": "plotly_white",
            "xaxis": {"visible": False, "scaleanchor": "y", "scaleratio": 1},
            "yaxis": {"visible": False},
            "margin": {"l": 20, "r": 20, "t": 50, "b": 20},
        }
        layout_options.update(kwargs)
        figure.update_layout(**layout_options)

        if show:
            figure.show()
        if export_path is not None:
            export_path = Path(export_path)
            if export_path.exists() and export_path.is_dir():
                output_file = export_path / f"{self.name}_plot.html"
                figure.write_html(output_file)
                logger.info(f"Plot saved to {output_file}")
            elif export_path.exists():
                raise NotADirectoryError("Provided path is not a directory")
            else:
                raise FileNotFoundError("Provided path does not exist")

        return figure

    def _build_plot_graph(self) -> nx.Graph:
        """Build a graph from terminal references for schematic plotting."""

        graph = nx.Graph()
        voltage_levels = {level.name: level for level in self.get_components(VoltageLevel)}
        connectivity_nodes = {node.name: node for node in self.get_components(ConnectivityNode)}
        busbar_sections = {
            busbar.connectivity_node_id: busbar for busbar in self.get_components(BusbarSection)
        }
        terminals = {terminal.name: terminal for terminal in self.get_components(Terminal)}
        self._add_plot_connectivity_nodes(
            graph, connectivity_nodes, busbar_sections, voltage_levels
        )
        self._add_plot_equipment_edges(
            graph, terminals, connectivity_nodes, busbar_sections, voltage_levels
        )
        self._add_plot_boundary_edges(
            graph, terminals, connectivity_nodes, busbar_sections, voltage_levels
        )
        self._add_plot_external_circuit_edges(
            graph, terminals, connectivity_nodes, busbar_sections, voltage_levels
        )
        return graph

    def _build_plot_positions(self, graph: nx.Graph) -> dict[str, tuple[float, float]]:
        """Return deterministic one-line positions for the station graph.

        Ordinary layouts are arranged in horizontal electrical layers, with
        busbars at the top and feeder boundaries at the bottom. A ring-bus
        cycle is laid out radially so its defining topology remains visible.
        """

        if not graph:
            return {}
        busbars = sorted(
            (node for node, data in graph.nodes(data=True) if data.get("kind") == "busbar"),
            key=self._plot_node_sort_key,
        )
        ring_cycle = self._find_ring_bus_cycle(graph, busbars)
        if ring_cycle is not None:
            positions = self._build_ring_plot_positions(graph, ring_cycle)
            return self._apply_diagram_positions(graph, positions)
        voltage_level_ids = {
            graph.nodes[node].get("voltage_level_id")
            for node in busbars
            if graph.nodes[node].get("voltage_level_id") is not None
        }
        if len(voltage_level_ids) > 1:
            positions = self._build_voltage_level_plot_positions(graph, busbars)
        else:
            positions = self._build_layered_plot_positions(graph, busbars)
        return self._apply_diagram_positions(graph, positions)

    def _apply_diagram_positions(
        self, graph: nx.Graph, positions: dict[str, tuple[float, float]]
    ) -> dict[str, tuple[float, float]]:
        """Apply authored schematic positions stored on the station system."""

        target_keys = {node.split(":", 1)[-1]: node for node in graph if ":" in node}
        authored_positions = {
            target_keys[position.target_id]: (position.x, position.y)
            for position in self.get_components(DiagramPosition)
            if position.target_id in target_keys
        }
        for busbar in (
            node for node, data in graph.nodes(data=True) if data.get("kind") == "busbar"
        ):
            diagram_start = graph.nodes[busbar].get("diagram_start")
            diagram_end = graph.nodes[busbar].get("diagram_end")
            if diagram_start is not None and diagram_end is not None:
                positions[busbar] = (
                    (diagram_start[0] + diagram_end[0]) / 2,
                    (diagram_start[1] + diagram_end[1]) / 2,
                )
        positions.update(authored_positions)
        self._position_internal_connectivity_nodes(graph, positions, target_keys)
        return positions

    def _position_internal_connectivity_nodes(self, graph, positions, target_keys) -> None:
        """Center unpinned junctions between their visible diagram neighbors."""

        pinned = {
            target_keys[position.target_id]
            for position in self.get_components(DiagramPosition)
            if position.target_id in target_keys
        }
        for _ in range(len(graph)):
            changed = False
            for node, data in graph.nodes(data=True):
                if data.get("kind") != "connectivity" or node in pinned:
                    continue
                neighbor_positions = [positions[neighbor] for neighbor in graph.neighbors(node)]
                if not neighbor_positions:
                    continue
                x = sum(position[0] for position in neighbor_positions) / len(neighbor_positions)
                y = sum(position[1] for position in neighbor_positions) / len(neighbor_positions)
                if positions.get(node) != (x, y):
                    positions[node] = (x, y)
                    changed = True
            if not changed:
                break

    def _build_voltage_level_plot_positions(
        self, graph: nx.Graph, busbars: list[str]
    ) -> dict[str, tuple[float, float]]:
        """Place buses on voltage-level rows and branches below their bus."""

        voltage_levels = self._plot_voltage_levels(graph, busbars)
        level_y = {level_id: -index * 5.0 for index, level_id in enumerate(voltage_levels)}
        busbars_by_level = {
            level_id: sorted(
                (
                    node
                    for node in busbars
                    if graph.nodes[node].get("voltage_level_id") == level_id
                ),
                key=self._plot_node_sort_key,
            )
            for level_id in voltage_levels
        }
        positions: dict[str, tuple[float, float]] = {}
        for level_id, level_busbars in busbars_by_level.items():
            for index, busbar in enumerate(level_busbars):
                x = (index - (len(level_busbars) - 1) / 2) * 4.0
                positions[busbar] = (x, level_y[level_id])

        self._plot_direct_equipment_positions(graph, busbars, positions, level_y)
        self._plot_branch_positions(graph, positions)

        remaining_nodes = [node for node in graph if node not in positions]
        if remaining_nodes:
            fallback = self._build_layered_plot_positions(graph, busbars)
            positions.update({node: fallback[node] for node in remaining_nodes})
        return positions

    @staticmethod
    def _plot_voltage_levels(graph: nx.Graph, busbars: list[str]) -> list[str]:
        """Sort voltage levels from highest nominal voltage to lowest."""

        levels: dict[str, float] = {}
        for busbar in busbars:
            data = graph.nodes[busbar]
            level_id = data.get("voltage_level_id")
            if level_id is not None:
                levels[level_id] = data.get("nominal_voltage_kv", 0.0)
        return sorted(levels, key=lambda level_id: (-levels[level_id], level_id))

    def _plot_direct_equipment_positions(self, graph, busbars, positions, level_y):
        """Place equipment connected directly to one or more busbars."""

        equipment_by_anchor: dict[tuple[str, ...], list[str]] = {}
        for equipment, data in graph.nodes(data=True):
            if data.get("kind") != "equipment":
                continue
            busbar_neighbors = [
                neighbor for neighbor in graph.neighbors(equipment) if neighbor in busbars
            ]
            if not busbar_neighbors:
                continue
            levels = {graph.nodes[busbar].get("voltage_level_id") for busbar in busbar_neighbors}
            if len(levels) > 1:
                x = sum(positions[busbar][0] for busbar in busbar_neighbors) / len(
                    busbar_neighbors
                )
                y = sum(positions[busbar][1] for busbar in busbar_neighbors) / len(
                    busbar_neighbors
                )
                positions[equipment] = (x, y)
                continue
            equipment_by_anchor.setdefault(tuple(sorted(busbar_neighbors)), []).append(equipment)

        for anchors, equipment_nodes in equipment_by_anchor.items():
            anchor_x = sum(positions[busbar][0] for busbar in anchors) / len(anchors)
            level_id = graph.nodes[anchors[0]].get("voltage_level_id")
            equipment_nodes.sort(key=self._plot_node_sort_key)
            for index, equipment in enumerate(equipment_nodes):
                x = anchor_x + (index - (len(equipment_nodes) - 1) / 2) * 2.5
                positions[equipment] = (x, level_y[level_id] - 1.5)

    @staticmethod
    def _plot_branch_positions(graph, positions) -> None:
        """Place unpositioned radial branches below their positioned parent."""

        queue = sorted(positions, key=SubstationSystem._plot_node_sort_key)
        for parent in queue:
            children = sorted(
                (neighbor for neighbor in graph.neighbors(parent) if neighbor not in positions),
                key=SubstationSystem._plot_node_sort_key,
            )
            if not children:
                continue
            parent_x, parent_y = positions[parent]
            for index, child in enumerate(children):
                x = parent_x + (index - (len(children) - 1) / 2) * 2.5
                positions[child] = (x, parent_y - 1.5)
            queue.extend(children)

    @staticmethod
    def _plot_node_sort_key(node: str) -> tuple:
        """Sort schematic nodes naturally by their display labels."""

        return tuple(
            (0, int(part)) if part.isdigit() else (1, part.casefold())
            for part in node.split(":", 1)[-1].replace("_", "-").split("-")
        )

    @staticmethod
    def _find_ring_bus_cycle(graph: nx.Graph, busbars: list[str]) -> list[str] | None:
        """Find a bus-to-bus breaker cycle, if the topology contains one."""

        bus_graph = nx.Graph()
        bus_graph.add_nodes_from(busbars)
        for equipment, data in graph.nodes(data=True):
            if data.get("kind") != "equipment":
                continue
            busbar_neighbors = [
                neighbor
                for neighbor in graph.neighbors(equipment)
                if graph.nodes[neighbor].get("kind") == "busbar"
            ]
            if len(busbar_neighbors) == 2:
                bus_graph.add_edge(*busbar_neighbors, equipment=equipment)

        cycles = [cycle for cycle in nx.cycle_basis(bus_graph) if len(cycle) >= 3]
        if not cycles:
            return None
        return max(cycles, key=lambda cycle: (len(cycle), tuple(sorted(cycle))))

    def _build_layered_plot_positions(
        self, graph: nx.Graph, busbars: list[str]
    ) -> dict[str, tuple[float, float]]:
        """Place graph nodes by shortest electrical distance from a busbar."""

        distances: dict[str, int] = {}
        for busbar in busbars:
            for node, distance in nx.single_source_shortest_path_length(graph, busbar).items():
                distances[node] = min(distance, distances.get(node, distance))

        unconnected_nodes = [node for node in graph if node not in distances]
        next_layer = max(distances.values(), default=0) + 2
        for index, node in enumerate(sorted(unconnected_nodes, key=self._plot_node_sort_key)):
            distances[node] = next_layer + index

        positions: dict[str, tuple[float, float]] = {}
        for layer in sorted(set(distances.values())):
            layer_nodes = sorted(
                (node for node, distance in distances.items() if distance == layer),
                key=self._plot_node_sort_key,
            )
            for index, node in enumerate(layer_nodes):
                x = (index - (len(layer_nodes) - 1) / 2) * 2.5
                if len(layer_nodes) == 1:
                    x = 0.0
                positions[node] = (x, -layer * 1.5)
        return positions

    def _build_ring_plot_positions(
        self, graph: nx.Graph, ring_cycle: list[str]
    ) -> dict[str, tuple[float, float]]:
        """Place a ring-bus cycle on a circle and branches radially outward."""

        ordered_cycle = self._order_ring_cycle(graph, ring_cycle)
        ring_busbars = set(ordered_cycle)
        ring_equipment = self._ring_equipment(graph, ring_busbars)
        positions: dict[str, tuple[float, float]] = {}
        busbar_radius = 3.0
        for index, busbar in enumerate(ordered_cycle):
            angle = math.pi / 2 - (2 * math.pi * index / len(ordered_cycle))
            positions[busbar] = (busbar_radius * math.cos(angle), busbar_radius * math.sin(angle))

        for equipment in ring_equipment:
            neighbors = [node for node in graph.neighbors(equipment) if node in ring_busbars]
            first, second = neighbors
            first_x, first_y = positions[first]
            second_x, second_y = positions[second]
            positions[equipment] = (
                (first_x + second_x) / 2,
                (first_y + second_y) / 2,
            )

        branch_nodes = set(graph) - ring_busbars - ring_equipment
        anchor, distances = self._ring_branch_distances(
            graph, ordered_cycle, ring_equipment, branch_nodes
        )
        grouped_branches: dict[str, list[str]] = {}
        for node in branch_nodes:
            if node in anchor:
                grouped_branches.setdefault(anchor[node], []).append(node)

        for branch_anchor, nodes in grouped_branches.items():
            busbar_x, busbar_y = positions[branch_anchor]
            base_angle = math.atan2(busbar_y, busbar_x)
            ordered_nodes = sorted(
                nodes,
                key=lambda node: (distances[node], self._plot_node_sort_key(node)),
            )
            for index, node in enumerate(ordered_nodes):
                angle = base_angle + (index - (len(ordered_nodes) - 1) / 2) * 0.12
                radius = busbar_radius + 1.4 * (distances[node] + 1)
                positions[node] = (radius * math.cos(angle), radius * math.sin(angle))

        remaining_nodes = [node for node in graph if node not in positions]
        if remaining_nodes:
            fallback = self._build_layered_plot_positions(graph, [])
            positions.update({node: fallback[node] for node in remaining_nodes})
        return positions

    @staticmethod
    def _order_ring_cycle(graph: nx.Graph, cycle: list[str]) -> list[str]:
        """Canonicalize a cycle so its orientation is stable between runs."""

        cycle_nodes = set(cycle)
        cycle_graph = nx.Graph()
        cycle_graph.add_nodes_from(cycle_nodes)
        for equipment, data in graph.nodes(data=True):
            if data.get("kind") != "equipment":
                continue
            neighbors = [
                neighbor for neighbor in graph.neighbors(equipment) if neighbor in cycle_nodes
            ]
            if len(neighbors) == 2:
                cycle_graph.add_edge(*neighbors)

        start = min(cycle_nodes, key=SubstationSystem._plot_node_sort_key)
        neighbors = sorted(
            cycle_graph.neighbors(start),
            key=SubstationSystem._plot_node_sort_key,
        )
        ordered = [start]
        previous = start
        current = neighbors[0]
        while current != start:
            ordered.append(current)
            next_nodes = [
                neighbor for neighbor in cycle_graph.neighbors(current) if neighbor != previous
            ]
            previous, current = current, next_nodes[0]
        return ordered

    @staticmethod
    def _ring_equipment(graph: nx.Graph, ring_busbars: set[str]) -> set[str]:
        return {
            node
            for node, data in graph.nodes(data=True)
            if data.get("kind") == "equipment"
            and len(set(graph.neighbors(node)) & ring_busbars) == 2
        }

    @staticmethod
    def _ring_branch_distances(graph, ring_cycle, ring_equipment, branch_nodes):
        """Assign each radial branch node to its ring busbar and distance."""

        ring_busbars = set(ring_cycle)
        anchor: dict[str, str] = {}
        distances: dict[str, int] = {}
        queue: list[str] = []
        for busbar in ring_cycle:
            for neighbor in graph.neighbors(busbar):
                if neighbor in ring_equipment or neighbor not in branch_nodes:
                    continue
                anchor[neighbor] = busbar
                distances[neighbor] = 1
                queue.append(neighbor)

        for node in queue:
            for neighbor in graph.neighbors(node):
                if neighbor in ring_busbars or neighbor in ring_equipment:
                    continue
                if neighbor in branch_nodes and neighbor not in anchor:
                    anchor[neighbor] = anchor[node]
                    distances[neighbor] = distances[node] + 1
                    queue.append(neighbor)
        return anchor, distances

    @staticmethod
    def _add_plot_connectivity_nodes(
        graph, connectivity_nodes, busbar_sections, voltage_levels
    ) -> None:
        for node in connectivity_nodes.values():
            SubstationSystem._add_plot_connectivity_node(
                graph, node.name, connectivity_nodes, busbar_sections, voltage_levels
            )
        for busbar in busbar_sections.values():
            SubstationSystem._add_plot_connectivity_node(
                graph,
                busbar.connectivity_node_id,
                connectivity_nodes,
                busbar_sections,
                voltage_levels,
            )

    @staticmethod
    def _add_plot_connectivity_node(
        graph,
        connectivity_node_id: str,
        connectivity_nodes,
        busbar_sections,
        voltage_levels,
    ) -> str:
        key = f"connectivity:{connectivity_node_id}"
        busbar = busbar_sections.get(connectivity_node_id)
        connectivity_node = connectivity_nodes.get(connectivity_node_id)
        if busbar is not None:
            voltage_level = voltage_levels.get(busbar.voltage_level_id)
            nominal_voltage_kv = SubstationSystem._voltage_kv(voltage_level)
            graph.add_node(
                key,
                kind="busbar",
                label=f"{busbar.name}<br>{SubstationSystem._voltage_label(nominal_voltage_kv)}",
                component_type=type(busbar).__name__,
                state=busbar.state.value,
                voltage_level_id=busbar.voltage_level_id,
                nominal_voltage_kv=nominal_voltage_kv,
                diagram_start=busbar.diagram_start,
                diagram_end=busbar.diagram_end,
            )
        elif connectivity_node is not None:
            voltage_level = voltage_levels.get(connectivity_node.voltage_level_id)
            graph.add_node(
                key,
                kind="connectivity",
                label=connectivity_node.name,
                component_type=type(connectivity_node).__name__,
                voltage_level_id=connectivity_node.voltage_level_id,
                nominal_voltage_kv=SubstationSystem._voltage_kv(voltage_level),
            )
        else:
            graph.add_node(
                key,
                kind="connectivity",
                label=connectivity_node_id,
                component_type="ConnectivityNode",
            )
        return key

    @staticmethod
    def _voltage_kv(voltage_level) -> float | None:
        if voltage_level is None:
            return None
        return float(voltage_level.nominal_voltage.to("kilovolt").magnitude)

    @staticmethod
    def _voltage_label(voltage_kv: float | None) -> str:
        return f"{voltage_kv:g} kV" if voltage_kv is not None else ""

    def _add_plot_equipment_edges(
        self, graph, terminals, connectivity_nodes, busbar_sections, voltage_levels
    ) -> None:
        for equipment in self.get_components(PrimaryEquipmentComponent):
            if isinstance(equipment, EarthingSwitch):
                continue
            equipment_key = f"equipment:{equipment.name}"
            equipment_state = getattr(equipment, "state", None)
            terminal_ids = equipment.terminal_ids or [getattr(equipment, "terminal_id", None)]
            winding_voltages = getattr(getattr(equipment, "equipment", None), "windings", [])
            voltage_label = "/".join(
                self._voltage_label(float(winding.rated_voltage.to("kilovolt").magnitude))
                for winding in winding_voltages
            )
            graph.add_node(
                equipment_key,
                kind="equipment",
                label=f"{equipment.name}<br>{voltage_label}" if voltage_label else equipment.name,
                component_type=type(equipment).__name__,
                state=equipment_state.value if equipment_state is not None else None,
                bay_id=equipment.bay_id,
            )
            for terminal_id in filter(None, terminal_ids):
                terminal = terminals.get(terminal_id)
                endpoint_key = self._plot_terminal_endpoint(
                    graph,
                    terminal_id,
                    terminals,
                    connectivity_nodes,
                    busbar_sections,
                    voltage_levels,
                )
                graph.add_edge(
                    equipment_key,
                    endpoint_key,
                    relation="terminal",
                    state=equipment_state.value if equipment_state is not None else None,
                    equipment=equipment.name,
                    terminal_position=terminal.diagram_position if terminal is not None else None,
                )

    def _add_plot_boundary_edges(
        self, graph, terminals, connectivity_nodes, busbar_sections, voltage_levels
    ) -> None:
        for boundary in self.get_components(FeederBoundary):
            boundary_key = f"boundary:{boundary.name}"
            graph.add_node(
                boundary_key,
                kind="feeder",
                label=boundary.feeder_id,
                component_type=type(boundary).__name__,
                bay_id=boundary.bay_id,
            )
            endpoint_key = self._plot_terminal_endpoint(
                graph,
                boundary.terminal_id,
                terminals,
                connectivity_nodes,
                busbar_sections,
                voltage_levels,
            )
            graph.add_edge(
                boundary_key,
                endpoint_key,
                relation="feeder boundary",
                state=None,
                equipment=boundary.feeder_id,
                terminal_position=terminals.get(boundary.terminal_id).diagram_position
                if boundary.terminal_id in terminals
                else None,
            )

    def _add_plot_external_circuit_edges(
        self, graph, terminals, connectivity_nodes, busbar_sections, voltage_levels
    ) -> None:
        for circuit in self.get_components(ExternalCircuit):
            circuit_key = f"circuit:{circuit.name}"
            graph.add_node(
                circuit_key,
                kind="circuit",
                label=f"{circuit.direction.value} {circuit.circuit_id}",
                component_type=type(circuit).__name__,
                bay_id=circuit.bay_id,
            )
            endpoint_key = self._plot_terminal_endpoint(
                graph,
                circuit.terminal_id,
                terminals,
                connectivity_nodes,
                busbar_sections,
                voltage_levels,
            )
            graph.add_edge(
                circuit_key,
                endpoint_key,
                relation="external circuit",
                state=None,
                equipment=circuit.circuit_id,
                terminal_position=terminals.get(circuit.terminal_id).diagram_position
                if circuit.terminal_id in terminals
                else None,
            )

    @staticmethod
    def _plot_terminal_endpoint(
        graph,
        terminal_id,
        terminals,
        connectivity_nodes,
        busbar_sections,
        voltage_levels,
    ) -> str:
        terminal = terminals.get(terminal_id)
        if terminal is not None:
            return SubstationSystem._add_plot_connectivity_node(
                graph,
                terminal.connectivity_node_id,
                connectivity_nodes,
                busbar_sections,
                voltage_levels,
            )
        terminal_key = f"terminal:{terminal_id}"
        graph.add_node(
            terminal_key,
            kind="terminal",
            label=terminal_id,
            component_type="Terminal",
        )
        return terminal_key

    @staticmethod
    def _add_plot_edge_trace(figure, graph: nx.Graph, positions) -> None:
        """Add schematic connection traces grouped by connection and state."""

        edge_groups: dict[tuple[str, str | None], dict[str, list]] = {}
        for source, target, edge_data in graph.edges(data=True):
            group_key = (edge_data["relation"], edge_data.get("state"))
            group = edge_groups.setdefault(group_key, {"x": [], "y": [], "text": []})
            source_x, source_y = positions[source]
            target_x, target_y = edge_data.get("terminal_position") or positions[target]
            terminal_position = edge_data.get("terminal_position")
            if terminal_position is not None:
                source_kind = graph.nodes[source].get("kind")
                target_kind = graph.nodes[target].get("kind")
                if source_kind in {"busbar", "connectivity"}:
                    source_x, source_y = terminal_position
                    target_x, target_y = positions[target]
                elif target_kind in {"busbar", "connectivity"}:
                    source_x, source_y = positions[source]
                    target_x, target_y = terminal_position
            hover_text = (
                f"<b>{edge_data['equipment']}</b><br>" f"Relation: {edge_data['relation']}"
            )
            if edge_data.get("state") is not None:
                hover_text += f"<br>State: {edge_data['state']}"
            group["x"].extend([source_x, target_x, None])
            group["y"].extend([source_y, target_y, None])
            group["text"].extend([hover_text, hover_text, None])

        for (relation, state), group in edge_groups.items():
            state_label = f" ({state})" if state else ""
            figure.add_trace(
                go.Scatter(
                    x=group["x"],
                    y=group["y"],
                    mode="lines",
                    line={
                        "color": "#7f8c8d" if relation == "terminal" else "#c0392b",
                        "dash": "dash" if state == EquipmentState.OPEN.value else "solid",
                        "width": 2,
                    },
                    text=group["text"],
                    hoverinfo="text",
                    name=f"{relation.title()}{state_label}",
                    legendgroup=f"{relation}-{state}",
                )
            )

    @staticmethod
    def _add_plot_busbar_traces(figure, graph: nx.Graph) -> None:
        """Draw explicitly authored busbar sections as schematic line segments."""

        x_values: list[float | None] = []
        y_values: list[float | None] = []
        hover_text: list[str | None] = []
        for _, data in graph.nodes(data=True):
            if data.get("kind") != "busbar":
                continue
            diagram_start = data.get("diagram_start")
            diagram_end = data.get("diagram_end")
            if diagram_start is None or diagram_end is None:
                continue
            x_values.extend([diagram_start[0], diagram_end[0], None])
            y_values.extend([diagram_start[1], diagram_end[1], None])
            hover = f"<b>{data['label']}</b><br>Busbar section"
            hover_text.extend([hover, hover, None])

        if x_values:
            figure.add_trace(
                go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode="lines",
                    line={"color": "#1f4e79", "width": 8},
                    text=hover_text,
                    hoverinfo="text",
                    name="Busbar",
                    legendgroup="busbar",
                )
            )

    @staticmethod
    def _add_plot_node_traces(figure, graph: nx.Graph, positions) -> None:
        """Add labeled schematic nodes grouped by electrical role."""

        styles = {
            "busbar": {"color": "#1f4e79", "symbol": "square", "size": 18},
            "equipment": {"color": "#d97706", "symbol": "circle", "size": 14},
            "feeder": {"color": "#b91c1c", "symbol": "triangle-right", "size": 16},
            "circuit": {"color": "#7c3aed", "symbol": "triangle-left", "size": 16},
            "connectivity": {"color": "#64748b", "symbol": "circle", "size": 8},
            "terminal": {"color": "#94a3b8", "symbol": "diamond", "size": 9},
        }
        grouped_nodes: dict[str, list[tuple[str, dict]]] = {}
        for node, node_data in graph.nodes(data=True):
            if node_data["kind"] == "busbar" and node_data.get("diagram_start") is not None:
                continue
            grouped_nodes.setdefault(node_data["kind"], []).append((node, node_data))

        for kind, nodes in grouped_nodes.items():
            if kind == "connectivity":
                continue
            style = styles[kind]
            labels = [node_data["label"].replace("-", "-<br>") for _, node_data in nodes]
            hover_text = []
            for _, node_data in nodes:
                text = f"<b>{node_data['label']}</b><br>Type: {node_data['component_type']}"
                if node_data.get("state") is not None:
                    text += f"<br>State: {node_data['state']}"
                if node_data.get("bay_id") is not None:
                    text += f"<br>Bay: {node_data['bay_id']}"
                hover_text.append(text)
            figure.add_trace(
                go.Scatter(
                    x=[positions[node][0] for node, _ in nodes],
                    y=[positions[node][1] for node, _ in nodes],
                    mode="markers+text",
                    marker={
                        "color": style["color"],
                        "symbol": style["symbol"],
                        "size": style["size"],
                        "line": {"color": "white", "width": 1},
                    },
                    text=labels,
                    textposition="top center",
                    hovertext=hover_text,
                    hoverinfo="text",
                    name=kind.title(),
                    legendgroup=kind,
                )
            )

    @classmethod
    def example(cls) -> "SubstationSystem":
        system = cls(auto_add_composed_components=True, name="example-substation")
        system.add_components(
            Substation.example(),
            VoltageLevel.example(),
            ConnectivityNode.example(),
            Bay.example(),
            BusbarSection.example(),
            Terminal.example(),
            FeederBoundary.example(),
        )
        return system


class Substation(Component):
    """Facility-level substation identity and applicability."""

    substation_type: SubstationType
    lifecycle_status: LifecycleStatus = LifecycleStatus.DESIGNED
    voltage_level_ids: list[str] = Field(default_factory=list)
    bay_ids: list[str] = Field(default_factory=list)
    feeder_boundary_ids: list[str] = Field(default_factory=list)
    asset_references: list[AssetReference] = Field(default_factory=list)
    external_identifiers: list[ExternalIdentifier] = Field(default_factory=list)
    model_references: list[ModelReference] = Field(default_factory=list)
    standard_profiles: list[StandardProfile] = Field(default_factory=list)
    lifecycle_records: list[LifecycleRecord] = Field(default_factory=list)
    document_references: list[DocumentReference] = Field(default_factory=list)
    ratings: list[Rating] = Field(default_factory=list)

    @classmethod
    def example(cls) -> "Substation":
        return cls(
            name="substation-001",
            substation_type=SubstationType.DISTRIBUTION,
            voltage_level_ids=["voltage-level-mv"],
            bay_ids=["feeder-bay-001"],
            feeder_boundary_ids=["feeder-boundary-001"],
        )
