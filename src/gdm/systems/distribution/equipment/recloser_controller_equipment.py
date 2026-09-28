"""This module stores recloser controller equipment."""

from infrasys import Component


class RecloserControllerEquipment(Component):
    """Class interface for recloser controller equipment."""

    @classmethod
    def example(cls) -> "RecloserControllerEquipment":
        """Example for matrix impedance recloser equipment."""
        return RecloserControllerEquipment(name="SEL-5460")
