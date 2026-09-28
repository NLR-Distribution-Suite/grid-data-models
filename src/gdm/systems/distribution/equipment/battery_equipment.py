"""This module contains solar equipment."""

from typing import Annotated

from infrasys import Component
from pydantic import Field

from gdm.quantities import ActivePower, EnergyDC, Voltage
from gdm.systems.distribution.enums import VoltageTypes
from gdm.constants import PINT_SCHEMA


class BatteryEquipment(Component):
    """Data model for Solar Model."""

    rated_energy: Annotated[
        EnergyDC,
        PINT_SCHEMA,
        Field(..., description="Rated energy capacity (DC) of the battery."),
    ]

    rated_power: Annotated[
        ActivePower,
        PINT_SCHEMA,
        Field(..., description="Rated power of the battery", ge=0),
    ]

    charging_efficiency: Annotated[
        float,
        Field(..., ge=0, le=100, description="Charging efficiency of the battery."),
    ]

    discharging_efficiency: Annotated[
        float,
        Field(..., ge=0, le=100, description="Discharging efficiency of the battery."),
    ]

    idling_efficiency: Annotated[
        float,
        Field(..., ge=0, le=100, description="Idling efficiency of the battery."),
    ]
    rated_voltage: Annotated[
        Voltage,
        Field(..., description="Rated voltage for this battery equipment.", ge=0),
    ]
    voltage_type: Annotated[
        VoltageTypes,
        Field(..., description="Rated voltage is line to line or line to neutral."),
    ]

    @classmethod
    def example(cls) -> "BatteryEquipment":
        "Example for a battery Equipment"
        return BatteryEquipment(
            name="battery-install1",
            rated_energy=EnergyDC(4, "kWh"),
            rated_power=ActivePower(1, "kW"),
            charging_efficiency=98,
            discharging_efficiency=98,
            idling_efficiency=99,
            rated_voltage=Voltage(12.47, "kilovolt"),
            voltage_type=VoltageTypes.LINE_TO_LINE,
        )
