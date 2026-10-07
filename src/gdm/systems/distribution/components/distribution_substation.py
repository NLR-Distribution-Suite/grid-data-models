"""This module contains basic model for distribution substation."""

from typing import Annotated

from infrasys import Component
from pydantic import Field

from gdm.systems.distribution.components.distribution_feeder import DistributionFeeder


class DistributionSubstation(Component):
    """Class interface for distribution feeder."""

    feeders: Annotated[
        list[DistributionFeeder], Field(..., description="List of feeders for this substation.")
    ]

    @classmethod
    def example(cls) -> "DistributionSubstation":
        return DistributionSubstation(
            name="test_substation",
            feeders=[DistributionFeeder.example()],
        )
