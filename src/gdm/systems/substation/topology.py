"""Substation facility and electrical topology models.

Station topology follows the bus-branch design used by ``DistributionSystem``.
Electrical nodes are :class:`BusbarSection` instances (a ``DistributionBus``
subclass) and primary equipment references the nodes it connects directly,
instead of using string IDs and terminal/connectivity-node indirection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from infrasys import Component, Location, System
from pydantic import Field

from gdm.constants import PINT_SCHEMA
from gdm.quantities import Distance, Frequency, Voltage
from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.systems.distribution.enums import (
    ColorLineBy,
    ColorNodeBy,
    MapType,
    Phase,
    PlotingStyle,
    VoltageTypes,
)
from gdm.systems.substation.enums import (
    CircuitDirection,
    EquipmentState,
    LifecycleStatus,
    SubstationType,
)
from gdm.systems.substation.models import (
    AssetReference,
    DocumentReference,
    ExternalIdentifier,
    LifecycleRecord,
    ModelReference,
    Rating,
    StandardProfile,
)

_PHASES = [Phase.A, Phase.B, Phase.C]


class VoltageLevel(Component):
    """Nominal voltage grouping within a substation."""

    nominal_voltage: Annotated[Voltage, PINT_SCHEMA, Field(..., gt=0)]
    voltage_type: VoltageTypes = VoltageTypes.LINE_TO_LINE
    frequency_hz: Annotated[Frequency, PINT_SCHEMA, Field(Frequency(60, "hertz"), gt=0)]
    phases: list[Phase] = Field(default_factory=lambda: list(_PHASES))
    standard_profile_id: str | None = None

    @classmethod
    def example(cls) -> "VoltageLevel":
        return cls(
            name="medium-voltage",
            nominal_voltage=Voltage(12.47, "kilovolt"),
            voltage_type=VoltageTypes.LINE_TO_LINE,
        )


class Bay(Component):
    """Functional substation equipment grouping."""

    voltage_level: VoltageLevel | None = None

    @classmethod
    def example(cls) -> "Bay":
        return cls(name="feeder-bay-001", voltage_level=VoltageLevel.example())


class BusbarSection(DistributionBus):
    """Electrical node in a station.

    A busbar section may be a physical busbar (``length`` set, drawn as a thick
    segment) or an electrical junction between series equipment. Geographic
    placement uses the inherited ``coordinate``.
    """

    voltage_type: VoltageTypes = VoltageTypes.LINE_TO_LINE
    phases: list[Phase] = Field(default_factory=lambda: list(_PHASES))
    voltage_level: VoltageLevel | None = None
    length: Annotated[Distance | None, PINT_SCHEMA, Field(None, gt=0)]
    state: EquipmentState = EquipmentState.CLOSED

    @classmethod
    def example(cls) -> "BusbarSection":
        return cls(
            name="mv-bus-section-1",
            voltage_level=VoltageLevel.example(),
            rated_voltage=Voltage(12.47, "kilovolt"),
            voltage_type=VoltageTypes.LINE_TO_LINE,
            phases=list(_PHASES),
            length=Distance(12, "meter"),
            coordinate=Location(x=0.0, y=0.0),
        )


class ExternalCircuit(Component):
    """Incoming or outgoing transmission, subtransmission, or distribution circuit."""

    circuit_id: str
    bus: BusbarSection
    direction: CircuitDirection
    voltage_level: VoltageLevel | None = None
    bay: Bay | None = None

    @classmethod
    def example(cls) -> "ExternalCircuit":
        return cls(
            name="incoming-line-001",
            circuit_id="incoming-line-001",
            bus=BusbarSection.example(),
            direction=CircuitDirection.INCOMING,
        )


class FeederBoundary(Component):
    """Contract between a substation station model and a distribution model."""

    feeder_id: str
    bus: BusbarSection
    substation: "Substation | None" = None
    voltage_level: VoltageLevel | None = None
    bay: Bay | None = None
    distribution_model_reference_id: str | None = None
    source_equivalent_id: str | None = None

    @classmethod
    def example(cls) -> "FeederBoundary":
        return cls(
            name="feeder-boundary-001",
            feeder_id="feeder-001",
            bus=BusbarSection.example(),
        )


class Substation(Component):
    """Facility-level substation identity and applicability."""

    substation_type: SubstationType
    location: Location | None = None
    lifecycle_status: LifecycleStatus = LifecycleStatus.DESIGNED
    voltage_levels: list[VoltageLevel] = Field(default_factory=list)
    bays: list[Bay] = Field(default_factory=list)
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
            voltage_levels=[VoltageLevel.example()],
            bays=[Bay.example()],
        )


class SubstationSystem(System):
    """Utility substation design and station-automation system."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.data_format_version:
            from importlib.metadata import version

            self.data_format_version = version("grid-data-models")

    def get_undirected_graph(self):
        """Build a bus-branch connectivity graph of the station.

        Nodes are :class:`BusbarSection` instances. Edges are primary equipment
        that connect two or more nodes in series. Shunt devices (surge
        arresters, earthing switches, shunt instrument transformers) are not
        edges. Edge metadata carries the device name, type, and switch state so
        downstream SCADA consumers can filter on state.
        """

        import networkx as nx

        from gdm.systems.substation.components import PrimaryEquipmentComponent

        graph = nx.MultiGraph()
        for bus in self.get_components(BusbarSection):
            graph.add_node(
                bus.name,
                is_busbar=bus.length is not None,
                voltage_level=bus.voltage_level.name if bus.voltage_level else None,
                voltage=bus.rated_voltage.magnitude,
                phases=[phase.value for phase in bus.phases],
                in_service=bus.in_service,
            )

        for device in self.get_components(PrimaryEquipmentComponent):
            buses = getattr(device, "buses", None)
            if not buses or len(buses) < 2:
                continue
            names = [bus.name for bus in buses]
            state = getattr(device, "state", EquipmentState.CLOSED)
            is_closed = state in (EquipmentState.CLOSED, EquipmentState.RACKED_IN)
            data = {
                "name": device.name,
                "type": type(device),
                "state": state.value,
                "is_closed": is_closed,
            }
            if len(names) == 2:
                graph.add_edge(names[0], names[1], **data)
            else:
                for other in names[1:]:
                    graph.add_edge(names[0], other, **data)
        return graph

    def to_gdf(self, export_file: Path | None = None):
        """Convert the station nodes and equipment edges to a GeoDataFrame."""

        from gdm.systems.substation.plot import build_substation_geodataframe

        return build_substation_geodataframe(self, export_file=export_file)

    def to_geojson(self, export_file: Path | str) -> None:
        """Export the station topology to a GeoJSON file."""

        from gdm.systems.substation.plot import export_substation_geojson

        export_substation_geojson(self, export_file)

    def plot(
        self,
        export_path: Path | None = None,
        show: bool = True,
        color_node_by: ColorNodeBy = ColorNodeBy.PHASE,
        color_line_by: ColorLineBy = ColorLineBy.EQUIPMENT_TYPE,
        show_legend: bool = True,
        map_type: MapType = MapType.SCATTER_GEO,
        style: PlotingStyle = PlotingStyle.CARTO_POSITRON,
        zoom_level: int = 11,
        **kwargs,
    ):
        """Plot the station on a geographic map using node ``coordinate`` values."""

        from gdm.systems.substation.plot import plot_substation

        return plot_substation(
            self,
            export_path=export_path,
            show=show,
            color_node_by=color_node_by,
            color_line_by=color_line_by,
            show_legend=show_legend,
            map_type=map_type,
            style=style,
            zoom_level=zoom_level,
            **kwargs,
        )

    @classmethod
    def example(cls) -> "SubstationSystem":
        from gdm.systems.substation.components import CircuitBreaker
        from gdm.systems.distribution.equipment import CircuitBreakerEquipment

        system = cls(auto_add_composed_components=True, name="example-substation")
        voltage_level = VoltageLevel.example()
        bus = BusbarSection(
            name="mv-bus-section-1",
            voltage_level=voltage_level,
            rated_voltage=Voltage(12.47, "kilovolt"),
            voltage_type=VoltageTypes.LINE_TO_LINE,
            phases=list(_PHASES),
            length=Distance(12, "meter"),
            coordinate=Location(x=0.0, y=0.0),
        )
        bay = Bay(name="feeder-bay-001", voltage_level=voltage_level)
        feeder_node = BusbarSection(
            name="feeder-node",
            voltage_level=voltage_level,
            rated_voltage=Voltage(12.47, "kilovolt"),
            phases=list(_PHASES),
        )
        breaker = CircuitBreaker(
            name="feeder-breaker-001",
            bay=bay,
            buses=[bus, feeder_node],
            equipment=CircuitBreakerEquipment.example(),
            state=EquipmentState.CLOSED,
            normal_state=EquipmentState.CLOSED,
        )
        substation = Substation(
            name="substation-001",
            substation_type=SubstationType.DISTRIBUTION,
            voltage_levels=[voltage_level],
            bays=[bay],
        )
        boundary = FeederBoundary(
            name="feeder-boundary-001",
            feeder_id="feeder-001",
            bus=feeder_node,
            substation=substation,
            voltage_level=voltage_level,
            bay=bay,
        )
        system.add_components(substation, bus, feeder_node, breaker, boundary)
        return system


# Resolve forward references created by the intra-module Substation <-> BusbarSection
# and Substation <-> FeederBoundary relationships.
for _model in (BusbarSection, FeederBoundary, Substation):
    _model.model_rebuild()
