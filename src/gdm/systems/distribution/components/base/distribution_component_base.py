"""This module contains class for managing basic fields for distribution assets."""

from typing_extensions import Annotated
from typing import Optional
from abc import ABC

from pydantic import Field
from infrasys import Component

from gdm.systems.distribution.components.distribution_feeder import DistributionFeeder
from gdm.systems.distribution.components.distribution_substation import DistributionSubstation


class DistributionComponentBase(Component, ABC):
    """Data model for simple distribution component."""

    substation: Annotated[
        Optional[DistributionSubstation], Field(None, description="Name of the substation.")
    ]
    feeder: Annotated[Optional[DistributionFeeder], Field(None, description="Name of the feeder.")]


class InServiceDistributionComponentBase(DistributionComponentBase, ABC):
    in_service: Annotated[bool, Field(True, description="Is the component in service?")]
