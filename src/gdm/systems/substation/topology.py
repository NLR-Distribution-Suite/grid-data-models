"""Substation facility and electrical topology models.

Station topology follows the bus-branch design used by ``DistributionSystem``.
Electrical nodes are :class:`BusbarSection` instances (a ``DistributionBus``
subclass) and primary equipment references the nodes it connects directly,
instead of using string IDs and terminal/connectivity-node indirection.
"""

from __future__ import annotations

from typing import Annotated

from infrasys import Component, Location
from pydantic import Field

from gdm.constants import PINT_SCHEMA
from gdm.quantities import Distance, Frequency, Voltage
from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.systems.distribution.enums import (
    Phase,
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


# Resolve forward references created by the intra-module Substation <-> BusbarSection
# and Substation <-> FeederBoundary relationships.
for _model in (BusbarSection, FeederBoundary, Substation):
    _model.model_rebuild()
