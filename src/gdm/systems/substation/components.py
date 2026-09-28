"""Installed substation primary components."""

from infrasys import Component
from pydantic import Field, model_validator

from gdm.systems.distribution.equipment import (
    CircuitBreakerEquipment,
    DisconnectorEquipment,
    EarthingSwitchEquipment,
    PowerTransformerEquipment,
)
from gdm.systems.substation.enums import EquipmentState, LifecycleStatus
from gdm.systems.substation.models import AssetReference, LifecycleRecord, Rating, StateObservation


class PrimaryEquipmentComponent(Component):
    """Installed station equipment with topology and asset-management data."""

    asset_reference: AssetReference | None = None
    bay_id: str | None = None
    terminal_ids: list[str] = Field(default_factory=list)
    lifecycle_status: LifecycleStatus = LifecycleStatus.DESIGNED
    ratings: list[Rating] = Field(default_factory=list)
    lifecycle_records: list[LifecycleRecord] = Field(default_factory=list)
    state_observations: list[StateObservation] = Field(default_factory=list)


class CircuitBreaker(PrimaryEquipmentComponent):
    """Installed circuit breaker referencing reusable electrical equipment."""

    equipment: CircuitBreakerEquipment
    state: EquipmentState = EquipmentState.OPEN
    normal_state: EquipmentState = EquipmentState.OPEN

    @model_validator(mode="after")
    def validate_terminals(self) -> "CircuitBreaker":
        if len(self.terminal_ids) != 2:
            raise ValueError("CircuitBreaker requires exactly two terminal_ids.")
        return self

    @classmethod
    def example(cls) -> "CircuitBreaker":
        return cls(
            name="feeder-breaker-001",
            bay_id="feeder-bay-001",
            terminal_ids=["feeder-breaker-bus-terminal", "feeder-breaker-feeder-terminal"],
            equipment=CircuitBreakerEquipment.example(),
            state=EquipmentState.CLOSED,
            normal_state=EquipmentState.CLOSED,
        )


class Disconnector(PrimaryEquipmentComponent):
    """Installed visible isolation switch referencing reusable electrical equipment."""

    equipment: DisconnectorEquipment
    state: EquipmentState = EquipmentState.OPEN
    normal_state: EquipmentState = EquipmentState.OPEN

    @model_validator(mode="after")
    def validate_terminals(self) -> "Disconnector":
        if len(self.terminal_ids) != 2:
            raise ValueError("Disconnector requires exactly two terminal_ids.")
        return self

    @classmethod
    def example(cls) -> "Disconnector":
        return cls(
            name="feeder-disconnector-001",
            bay_id="feeder-bay-001",
            terminal_ids=["disconnector-bus-terminal", "disconnector-feeder-terminal"],
            equipment=DisconnectorEquipment.example(),
        )


class EarthingSwitch(PrimaryEquipmentComponent):
    """Installed safety-ground switch referencing reusable electrical equipment."""

    equipment: EarthingSwitchEquipment
    state: EquipmentState = EquipmentState.OPEN
    target_terminal_id: str

    @classmethod
    def example(cls) -> "EarthingSwitch":
        return cls(
            name="feeder-ground-switch-001",
            bay_id="feeder-bay-001",
            target_terminal_id="disconnector-feeder-terminal",
            equipment=EarthingSwitchEquipment.example(),
        )


class PowerTransformer(PrimaryEquipmentComponent):
    """Installed station transformer referencing reusable electrical equipment."""

    equipment: PowerTransformerEquipment
    winding_terminal_ids: list[str]
    tap_positions: list[list[float]] | None = None

    @model_validator(mode="after")
    def validate_windings(self) -> "PowerTransformer":
        if len(self.equipment.windings) < 2:
            raise ValueError("PowerTransformer requires at least two equipment windings.")
        if len(self.winding_terminal_ids) != len(self.equipment.windings):
            raise ValueError("PowerTransformer requires one terminal ID per equipment winding.")
        if len(set(self.winding_terminal_ids)) != len(self.winding_terminal_ids):
            raise ValueError("Each transformer winding must have a unique terminal_id.")
        if self.terminal_ids != self.winding_terminal_ids:
            raise ValueError("terminal_ids must match winding_terminal_ids in winding order.")
        return self

    @classmethod
    def example(cls) -> "PowerTransformer":
        terminal_ids = ["transformer-hv-terminal", "transformer-lv-terminal"]
        return cls(
            name="main-transformer-001",
            bay_id="transformer-bay-001",
            terminal_ids=terminal_ids,
            winding_terminal_ids=terminal_ids,
            equipment=PowerTransformerEquipment.example(),
        )
