"""Component model for a series distribution reactor."""

from typing import Annotated

from pydantic import Field

from gdm.quantities import Distance
from gdm.systems.distribution.components.base.distribution_branch_base import (
    DistributionBranchBase,
)
from gdm.systems.distribution.equipment.reactor_equipment import ReactorEquipment


class DistributionReactor(DistributionBranchBase):
    """A two-terminal series reactor between distribution buses.

    ``length`` is retained because reactors participate in the distribution
    graph through the branch convention. It is a bookkeeping length; the
    impedance is stored directly in ``ReactorEquipment``.
    """

    equipment: Annotated[ReactorEquipment, Field(..., description="Reactor equipment.")]

    @classmethod
    def example(cls) -> "DistributionReactor":
        from gdm.systems.distribution.components.distribution_bus import DistributionBus
        from gdm.systems.distribution.enums import Phase
        from gdm.quantities import Voltage

        bus1 = DistributionBus(
            name="reactor_source_bus",
            phases=[Phase.A, Phase.B, Phase.C],
            rated_voltage=Voltage(115, "kilovolt"),
            voltage_type="line-to-ground",
        )
        bus2 = DistributionBus(
            name="reactor_load_bus",
            phases=[Phase.A, Phase.B, Phase.C],
            rated_voltage=Voltage(115, "kilovolt"),
            voltage_type="line-to-ground",
        )
        return cls(
            name="reactor",
            buses=[bus1, bus2],
            length=Distance(1, "meter"),
            phases=[Phase.A, Phase.B, Phase.C],
            equipment=ReactorEquipment.example(),
        )
