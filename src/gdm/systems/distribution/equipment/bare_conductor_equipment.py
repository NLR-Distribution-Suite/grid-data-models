"""This module contains bare conductor equipment."""

from typing import Annotated

from infrasys import Component
from pydantic import Field

from gdm.quantities import (
    ResistancePULength,
    Distance,
    Current,
)
from gdm.constants import PINT_SCHEMA


class BareConductorEquipment(Component):
    """Data model for conductor catalaog."""

    conductor_diameter: Annotated[
        Distance, PINT_SCHEMA, Field(..., description="Diameter of the conductor.", gt=0)
    ]
    conductor_gmr: Annotated[
        Distance,
        PINT_SCHEMA,
        Field(..., description="Geometric mean radius of the conductor.", gt=0),
    ]
    ampacity: Annotated[
        Current,
        PINT_SCHEMA,
        Field(..., description="Ampacity of the conductor.", gt=0),
    ]
    ac_resistance: Annotated[
        ResistancePULength,
        PINT_SCHEMA,
        Field(
            ...,
            description="Per unit length positive alternating current resistance of the conductor.",
            gt=0,
        ),
    ]
    emergency_ampacity: Annotated[
        Current,
        PINT_SCHEMA,
        Field(..., description="Emergency ampacity for this conductor.", gt=0),
    ]
    dc_resistance: Annotated[
        ResistancePULength,
        PINT_SCHEMA,
        Field(
            ...,
            description="Per unit length positive direct current resistance of the conductor.",
            gt=0,
        ),
    ]

    @classmethod
    def example(cls) -> "BareConductorEquipment":
        """Example for bare conductor."""
        return BareConductorEquipment(
            name="24_AWGSLD_Copper",
            conductor_diameter=Distance(0.0201, "in"),
            conductor_gmr=Distance(0.00065, "ft"),
            ampacity=Current(1, "ampere"),
            ac_resistance=ResistancePULength(151.62, "ohm/m"),
            dc_resistance=ResistancePULength(151.62, "ohm/m"),
            emergency_ampacity=Current(1, "ampere"),
        )
