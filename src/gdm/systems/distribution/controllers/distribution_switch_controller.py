"""This module contains distribution switch controller."""

from typing import Annotated, Literal

from pydantic import Field
from infrasys.quantities import Time
from infrasys import Component

from gdm.constants import PINT_SCHEMA


class DistributionSwitchController(Component):
    """Data model for distribution switch controller."""

    name: Annotated[str, Field("", description="Name of the switch controller.")]

    delay: Annotated[
        Time, PINT_SCHEMA, Field(description="Fixed delay added to the recloser trip time.")
    ]

    normal_state: Annotated[
        Literal["open", "close"],
        Field(..., description="Action to open or close the switch after delay time."),
    ]
    is_locked: Annotated[
        bool, Field(description="Boolean value representing whether the switch is locked or not.")
    ]

    @classmethod
    def example(cls) -> "DistributionSwitchController":
        """Example for distribution switch controller."""
        return DistributionSwitchController(
            delay=Time(0, "minutes"), normal_state="close", is_locked=False
        )
