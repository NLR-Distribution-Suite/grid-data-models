"""This module contains capacitor equipment."""

from typing import Annotated

from infrasys import Component
from pydantic import Field

from gdm.systems.distribution.equipment.phase_capacitor_equipment import PhaseCapacitorEquipment
from gdm.systems.distribution.enums import ConnectionType, VoltageTypes
from gdm.quantities import Voltage


class CapacitorEquipment(Component):
    """Data model for capacitor model."""

    phase_capacitors: Annotated[
        list[PhaseCapacitorEquipment],
        Field(
            ...,
            description="List of phase capacitors for this distribution capacitor.",
        ),
    ]
    connection_type: Annotated[
        ConnectionType,
        Field(ConnectionType.STAR, description="Connection type for this capacitor."),
    ]
    rated_voltage: Annotated[
        Voltage,
        Field(..., description="Rated voltage for this capacitor.", gt=0),
    ]
    voltage_type: Annotated[
        VoltageTypes,
        Field(..., description="Rated voltage is line to line or line to neutral."),
    ]

    @classmethod
    def example(cls) -> "CapacitorEquipment":
        """Example for capacitor model."""
        return CapacitorEquipment(
            name="capacitor-equipment-1",
            phase_capacitors=[PhaseCapacitorEquipment.example()] * 3,
            connection_type=ConnectionType.STAR,
            rated_voltage=Voltage(12.47, "kilovolt"),
            voltage_type=VoltageTypes.LINE_TO_LINE,
        )
