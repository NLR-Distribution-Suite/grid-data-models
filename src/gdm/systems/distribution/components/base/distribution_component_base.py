"""This module contains class for managing basic fields for distribution assets."""

from typing_extensions import Annotated
from typing import Optional, TypeVar
from abc import ABC

from pydantic import Field
from infrasys import Component
from loguru import logger

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


_ComponentT = TypeVar("_ComponentT", bound=Component)


def _in_service_components(
    instances: list[_ComponentT], *, require_nonempty: bool = True
) -> list[_ComponentT]:
    active = []
    for component in instances:
        if not getattr(component, "in_service", True):
            logger.info(
                "Excluding out-of-service {} {} from aggregation",
                type(component).__name__,
                component.name,
            )
        else:
            active.append(component)
    if require_nonempty and not active:
        raise ValueError("Cannot aggregate without in-service components.")
    return active
