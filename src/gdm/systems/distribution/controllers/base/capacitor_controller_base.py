from typing import Annotated, Optional
from abc import ABC

from infrasys import Component
from infrasys.quantities import Time
from pydantic import Field


from gdm.constants import PINT_SCHEMA


class CapacitorControllerBase(Component, ABC):
    """Data model for capacitor controllers. Phase connection specified in the capacitor."""

    name: Annotated[str, Field("", description="Name of the capacitor controller.")]
    delay_on: Annotated[
        Optional[Time],
        PINT_SCHEMA,
        Field(
            None,
            description="The time that the capacitor needs to connect or disconnect when switching on",
        ),
    ]
    delay_off: Annotated[
        Optional[Time],
        PINT_SCHEMA,
        Field(
            None,
            description="The time that the capacitor needs to connect or disconnect when switching off",
        ),
    ]
    dead_time: Annotated[
        Optional[Time],
        PINT_SCHEMA,
        Field(
            None,
            description="The time that the capacitor must remain off before turning back on again",
        ),
    ]
