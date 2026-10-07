from typing import Annotated
from abc import ABC

from infrasys import Component
from pydantic import Field


class ActivePowerInverterControllerBase(Component, ABC):
    """Data model for Inverter controllers that control active power."""

    name: Annotated[str, Field("", description="Name of the inverter controller.")]


class ReactivePowerInverterControllerBase(Component, ABC):
    """Data model for Inverter controllers that control reactive power."""

    name: Annotated[str, Field("", description="Name of the inverter controller.")]
