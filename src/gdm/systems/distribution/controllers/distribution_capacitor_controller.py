"""This module contains interface for distribution capacitor controllers."""

from typing import Annotated
import datetime

from infrasys.quantities import Time
from pydantic import Field

from gdm.quantities import (
    ActivePower,
    ReactivePower,
    Voltage,
    Current,
)
from gdm.systems.distribution.controllers.base.capacitor_controller_base import (
    CapacitorControllerBase,
)
from gdm.constants import PINT_SCHEMA


class VoltageCapacitorController(CapacitorControllerBase):
    """Data model for a Capacitor Controller which uses voltage."""

    on_voltage: Annotated[
        Voltage,
        PINT_SCHEMA,
        Field(
            ...,
            description="Value of the controller voltage, above which the capacitor switches on.",
            gt=0,
        ),
    ]

    off_voltage: Annotated[
        Voltage,
        PINT_SCHEMA,
        Field(
            ..., description="Value of the voltage, below which the capacitors switches off.", gt=0
        ),
    ]

    pt_ratio: Annotated[
        float,
        Field(
            ...,
            ge=0,
            description="Value of the voltage (potential) transformer ratio used to step down the voltage for the controller.",
        ),
    ]

    @classmethod
    def example(cls) -> "VoltageCapacitorController":
        """Example for a VoltageCapacitorController."""
        return VoltageCapacitorController(
            delay_on=Time(20, "seconds"),
            pt_ratio=60,
            on_voltage=Voltage(125, "volt"),
            off_voltage=Voltage(120, "volt"),
        )


class ActivePowerCapacitorController(CapacitorControllerBase):
    """Data model for a Capacitor Controller which uses active power."""

    on_power: Annotated[
        ActivePower,
        PINT_SCHEMA,
        Field(
            ...,
            description="Value of the active power, above which the capacitor switches on.",
            ge=0,
        ),
    ]

    off_power: Annotated[
        ActivePower,
        PINT_SCHEMA,
        Field(
            ...,
            description="Value of the active power, below which the capacitor switches off.",
            gt=0,
        ),
    ]

    @classmethod
    def example(cls) -> "ActivePowerCapacitorController":
        """Example for an ActivePowerCapacitorController."""
        return ActivePowerCapacitorController(
            delay_on=Time(20, "seconds"),
            on_power=ActivePower(300, "kW"),
            off_power=ActivePower(300, "kW"),
        )


class ReactivePowerCapacitorController(CapacitorControllerBase):
    """Data model for a Capacitor Controller which uses reactive power."""

    on_power: Annotated[
        ReactivePower,
        PINT_SCHEMA,
        Field(
            ...,
            description="Value of the reactive power, above which the capacitor switches on.",
            gt=0,
        ),
    ]

    off_power: Annotated[
        ReactivePower,
        PINT_SCHEMA,
        Field(
            ...,
            description="Value of the reactive power, below which the capacitor switches off.",
            gt=0,
        ),
    ]

    @classmethod
    def example(cls) -> "ReactivePowerCapacitorController":
        """Example for an ReactivePowerCapacitorController."""
        return ReactivePowerCapacitorController(
            delay_on=Time(20, "seconds"),
            on_power=ReactivePower(300, "kvar"),
            off_power=ReactivePower(300, "kvar"),
        )


class CurrentCapacitorController(CapacitorControllerBase):
    """Data model for a Capacitor Controller which uses current."""

    on_current: Annotated[
        Current,
        PINT_SCHEMA,
        Field(
            ...,
            description="Value of the controller current, above which the capacitor switches on.",
            gt=0,
        ),
    ]

    off_current: Annotated[
        Current,
        PINT_SCHEMA,
        Field(
            ...,
            description="Value of the controller current, below which the capacitor switches off.",
            ge=0,
        ),
    ]

    ct_ratio: Annotated[
        float,
        Field(
            ...,
            ge=0,
            description="The current transformer ratio used to step down the current for the controller.",
        ),
    ]

    @classmethod
    def example(cls) -> "CurrentCapacitorController":
        """Example for a CurrentCapacitorController."""
        return CurrentCapacitorController(
            delay_on=Time(20, "seconds"),
            ct_ratio=10,
            on_current=Current(110, "ampere"),
            off_current=Current(110, "ampere"),
        )


class DailyTimedCapacitorController(CapacitorControllerBase):
    """Data model for a Capacitor Controller which uses a timed controller."""

    on_time: Annotated[
        datetime.time, Field(..., description="Time at which the capacitor switches on.")
    ]

    off_time: Annotated[
        datetime.time, Field(..., description="Time at which the capacitor switches off.")
    ]

    @classmethod
    def example(cls) -> "DailyTimedCapacitorController":
        """Example for a DailyTimedCapacitorController."""
        return DailyTimedCapacitorController(
            delay_on=Time(20, "seconds"),
            on_time=datetime.time(hour=9),
            off_time=datetime.time(hour=17),
        )
