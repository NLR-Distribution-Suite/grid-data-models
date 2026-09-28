"""This module contains interface for operation limit sets."""

from typing import Annotated
from infrasys import Component
from pydantic import Field

from gdm.quantities import Current, Voltage
from gdm.systems.distribution.enums import LimitType
from gdm.constants import PINT_SCHEMA


class VoltageLimitSet(Component):
    """Data model for voltage limit set."""

    name: Annotated[str, Field("", description="Name of the voltage limit set.")]
    limit_type: Annotated[LimitType, Field(..., description="Limit type used.")]
    value: Annotated[
        Voltage,
        PINT_SCHEMA,
        Field(..., description="Voltage threshold.", gt=0),
    ]

    @classmethod
    def example(cls) -> "VoltageLimitSet":
        """Example for voltage limit set."""
        return VoltageLimitSet(limit_type=LimitType.MIN, value=Voltage(400 * 0.9, "volt"))


class ThermalLimitSet(Component):
    """Data model for voltage limit set."""

    name: Annotated[str, Field("", description="Name of the thermal limit set.")]
    limit_type: Annotated[LimitType, Field(..., description="Limit type used.")]
    value: Annotated[Current, PINT_SCHEMA, Field(..., description="Current threshold.", gt=0)]

    @classmethod
    def example(cls) -> "ThermalLimitSet":
        """Example for thermal limit set."""
        return ThermalLimitSet(limit_type=LimitType.MAX, value=Current(110, "ampere"))
