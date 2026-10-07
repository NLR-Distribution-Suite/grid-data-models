"""Station switching equipment definitions."""

from pydantic import Field

from gdm.systems.distribution.equipment.matrix_impedance_switch_equipment import (
    MatrixImpedanceSwitchEquipment,
)


class CircuitBreakerEquipment(MatrixImpedanceSwitchEquipment):
    """Reusable electrical and interrupting ratings for a circuit breaker."""

    interrupting_current: float | None = Field(None, ge=0)
    interrupting_current_unit: str = "kiloampere"
    trip_circuit_count: int = Field(1, ge=1)

    @classmethod
    def example(cls) -> "CircuitBreakerEquipment":
        return cls(
            **MatrixImpedanceSwitchEquipment.example().model_dump(exclude_none=True),
            interrupting_current=25,
        )


class DisconnectorEquipment(MatrixImpedanceSwitchEquipment):
    """Reusable electrical ratings for a visible isolation switch."""

    @classmethod
    def example(cls) -> "DisconnectorEquipment":
        return cls(**MatrixImpedanceSwitchEquipment.example().model_dump(exclude_none=True))


class EarthingSwitchEquipment(MatrixImpedanceSwitchEquipment):
    """Reusable electrical ratings for an earthing switch."""

    @classmethod
    def example(cls) -> "EarthingSwitchEquipment":
        return cls(**MatrixImpedanceSwitchEquipment.example().model_dump(exclude_none=True))
