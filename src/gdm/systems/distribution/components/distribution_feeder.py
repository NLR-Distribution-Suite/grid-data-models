"""This module contains pydantic model for distribution feeder."""

from infrasys import Component


class DistributionFeeder(Component):
    """Class interface for distribution feeder."""

    @classmethod
    def example(cls) -> "DistributionFeeder":
        return DistributionFeeder(name="test_feeder")
