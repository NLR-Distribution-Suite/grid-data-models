"""Installed substation primary components.

Installed equipment references reusable distribution equipment definitions and
connects directly to :class:`BusbarSection` nodes, mirroring the bus-branch
design used by ``DistributionSystem``.
"""

from __future__ import annotations

from infrasys import Component
from pydantic import Field, model_validator

from gdm.quantities import Voltage
from gdm.systems.distribution.enums import Phase
from gdm.systems.distribution.equipment import (
    CircuitBreakerEquipment,
    DisconnectorEquipment,
    EarthingSwitchEquipment,
    PowerTransformerEquipment,
)
from gdm.systems.substation.enums import EquipmentState, LifecycleStatus
from gdm.systems.substation.models import AssetReference, LifecycleRecord, Rating, StateObservation
from gdm.systems.substation.topology import Bay, BusbarSection, VoltageLevel

_PHASES = [Phase.A, Phase.B, Phase.C]


class PrimaryEquipmentComponent(Component):
    """Installed station equipment with topology, bay, and asset-management data."""

    asset_reference: AssetReference | None = None
    bay: Bay | None = None
    voltage_level: VoltageLevel | None = None
    phases: list[Phase] = Field(default_factory=lambda: list(_PHASES))
    lifecycle_status: LifecycleStatus = LifecycleStatus.DESIGNED
    ratings: list[Rating] = Field(default_factory=list)
    lifecycle_records: list[LifecycleRecord] = Field(default_factory=list)
    state_observations: list[StateObservation] = Field(default_factory=list)


class TwoTerminalEquipment(PrimaryEquipmentComponent):
    """Equipment connected in series between exactly two busbar nodes."""

    buses: list[BusbarSection]

    @model_validator(mode="after")
    def validate_buses(self) -> "TwoTerminalEquipment":
        if len(self.buses) != 2:
            raise ValueError(f"{type(self).__name__} requires exactly two buses.")
        if self.buses[0].name == self.buses[1].name:
            raise ValueError(f"{type(self).__name__} requires two distinct buses.")
        return self


class CircuitBreaker(TwoTerminalEquipment):
    """Installed circuit breaker referencing reusable electrical equipment."""

    equipment: CircuitBreakerEquipment
    state: EquipmentState = EquipmentState.OPEN
    normal_state: EquipmentState = EquipmentState.OPEN

    @classmethod
    def example(cls) -> "CircuitBreaker":
        voltage_level = VoltageLevel.example()
        bus = BusbarSection.example()
        feeder_node = BusbarSection(
            name="feeder-node",
            voltage_level=voltage_level,
            rated_voltage=Voltage(12.47, "kilovolt"),
        )
        return cls(
            name="feeder-breaker-001",
            buses=[bus, feeder_node],
            equipment=CircuitBreakerEquipment.example(),
            state=EquipmentState.CLOSED,
            normal_state=EquipmentState.CLOSED,
        )


class Disconnector(TwoTerminalEquipment):
    """Installed visible isolation switch referencing reusable electrical equipment."""

    equipment: DisconnectorEquipment
    state: EquipmentState = EquipmentState.OPEN
    normal_state: EquipmentState = EquipmentState.OPEN

    @classmethod
    def example(cls) -> "Disconnector":
        voltage_level = VoltageLevel.example()
        bus = BusbarSection.example()
        feeder_node = BusbarSection(
            name="feeder-node",
            voltage_level=voltage_level,
            rated_voltage=Voltage(12.47, "kilovolt"),
        )
        return cls(
            name="feeder-disconnector-001",
            buses=[bus, feeder_node],
            equipment=DisconnectorEquipment.example(),
        )


class EarthingSwitch(PrimaryEquipmentComponent):
    """Installed safety-ground switch referencing reusable electrical equipment."""

    equipment: EarthingSwitchEquipment
    bus: BusbarSection
    state: EquipmentState = EquipmentState.OPEN

    @classmethod
    def example(cls) -> "EarthingSwitch":
        return cls(
            name="feeder-ground-switch-001",
            bus=BusbarSection.example(),
            equipment=EarthingSwitchEquipment.example(),
        )


class PowerTransformer(PrimaryEquipmentComponent):
    """Installed station transformer referencing reusable electrical equipment."""

    equipment: PowerTransformerEquipment
    buses: list[BusbarSection]
    tap_positions: list[list[float]] | None = None

    @model_validator(mode="after")
    def validate_windings(self) -> "PowerTransformer":
        if len(self.equipment.windings) < 2:
            raise ValueError("PowerTransformer requires at least two equipment windings.")
        if len(self.buses) != len(self.equipment.windings):
            raise ValueError("PowerTransformer requires one bus per equipment winding.")
        if len({bus.name for bus in self.buses}) != len(self.buses):
            raise ValueError("Each transformer winding must connect to a distinct bus.")
        return self

    @classmethod
    def example(cls) -> "PowerTransformer":
        hv_level = VoltageLevel(
            name="high-voltage",
            nominal_voltage=Voltage(69, "kilovolt"),
        )
        lv_level = VoltageLevel.example()
        hv_bus = BusbarSection(
            name="hv-bus",
            voltage_level=hv_level,
            rated_voltage=Voltage(69, "kilovolt"),
        )
        lv_bus = BusbarSection(
            name="lv-bus",
            voltage_level=lv_level,
            rated_voltage=Voltage(12.47, "kilovolt"),
        )
        return cls(
            name="main-transformer-001",
            buses=[hv_bus, lv_bus],
            equipment=PowerTransformerEquipment.example(),
        )
