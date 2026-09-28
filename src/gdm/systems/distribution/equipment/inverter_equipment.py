"""This module contains load equipment."""

from typing import Annotated, Optional

from infrasys import Component
from pydantic import Field

from gdm.quantities import ApparentPower, ActivePowerOverTime
from gdm.systems.distribution.common.curve import Curve
from gdm.constants import PINT_SCHEMA


class InverterEquipment(Component):
    """Data model for inverter equipment."""

    name: Annotated[str, Field("", description="Name of the inverter controller.")]
    rated_apparent_power: Annotated[
        ApparentPower,
        PINT_SCHEMA,
        Field(..., description="Apparent power rating for the inverter.", gt=0),
    ]
    rise_limit: Annotated[
        Optional[ActivePowerOverTime],
        PINT_SCHEMA,
        Field(..., description="The rise in power output allowed per unit of time"),
    ]

    fall_limit: Annotated[
        Optional[ActivePowerOverTime],
        PINT_SCHEMA,
        Field(..., description="The fall in power output allowed per unit of time"),
    ]
    cutout_percent: Annotated[
        float,
        Field(
            ge=0,
            le=100,
            description="If the per-unit power drops below this value the PV output is turned off.",
        ),
    ]
    cutin_percent: Annotated[
        float,
        Field(
            ge=0,
            le=100,
            description="If the per-unit power rises above this value the PV output is turned on.",
        ),
    ]
    dc_to_ac_efficiency: Annotated[
        float, Field(..., ge=0, le=100, description="DC to AC efficiency of the inverter.")
    ]
    eff_curve: Annotated[Optional[Curve], Field(None, description="Efficency curve for inverter.")]

    @classmethod
    def example(cls) -> "InverterEquipment":
        """Example for load model."""
        return InverterEquipment(
            rated_apparent_power=ApparentPower(3.8, "kva"),
            rise_limit=ActivePowerOverTime(1.1, "kW/second"),
            fall_limit=ActivePowerOverTime(1.1, "kW/second"),
            dc_to_ac_efficiency=100,
            cutout_percent=10,
            cutin_percent=10,
        )
