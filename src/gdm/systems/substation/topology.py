"""Substation facility and electrical topology models."""

from typing import Annotated

from infrasys import Component, Location, System
from pydantic import Field

from gdm.constants import PINT_SCHEMA
from gdm.quantities import Distance, Voltage
from gdm.systems.distribution.enums import Phase, VoltageTypes
from gdm.systems.substation.enums import (
    CircuitDirection,
    EquipmentState,
    LifecycleStatus,
    SubstationType,
    TerminalRole,
)
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

    @classmethod
    def example(cls) -> "Terminal":
        return cls(
            name="feeder-breaker-feeder-terminal",
            connectivity_node_id="mv-bus-node",
            phases=[Phase.A, Phase.B, Phase.C],
            role=TerminalRole.FEEDER_SIDE,
            equipment_id="feeder-breaker-001",
        )


class Bay(Component):
    """Functional substation equipment grouping."""

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

    @classmethod
    def example(cls) -> "BusbarSection":
        return cls(
            name="mv-bus-section-1",
            voltage_level_id="voltage-level-mv",
            connectivity_node_id="mv-bus-node",
            phases=[Phase.A, Phase.B, Phase.C],
            length=Distance(12, "meter"),
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


class SubstationSystem(System):
    """Utility substation design and station-automation system."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.data_format_version:
            from importlib.metadata import version

            self.data_format_version = version("grid-data-models")

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
    location: Location | None = None
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
