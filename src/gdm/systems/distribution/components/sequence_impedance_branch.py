"""This module contains sequence impedance branch."""

from typing import Annotated

from pydantic import Field, model_validator

from gdm.systems.distribution.components.base.distribution_branch_base import (
    DistributionBranchBase,
)
from gdm.systems.distribution.components.distribution_feeder import DistributionFeeder
from gdm.systems.distribution.components.distribution_substation import DistributionSubstation
from gdm.systems.distribution.equipment.sequence_impedance_branch_equipment import (
    SequenceImpedanceBranchEquipment,
)
from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.systems.distribution.enums import Phase
from gdm.quantities import Voltage, Distance


class SequenceImpedanceBranch(DistributionBranchBase):
    """Data model for sequence impedance branch."""

    equipment: Annotated[
        SequenceImpedanceBranchEquipment, Field(..., description="Sequence impedance branch.")
    ]

    @model_validator(mode="after")
    def validate_fields(self) -> "SequenceImpedanceBranch":
        """Custom validator for sequence impedance branch."""
        if len(self.phases) == 1:
            msg = f"Sequence impedance assigned to single phase {self.phases=}"
            raise ValueError(msg)
        return self

    @classmethod
    def example(cls) -> "SequenceImpedanceBranch":
        """Example for sequence impedance branch."""
        bus1 = DistributionBus(
            voltage_type="line-to-ground",
            phases=[Phase.A, Phase.B, Phase.C],
            rated_voltage=Voltage(400, "volt"),
            substation=DistributionSubstation.example(),
            feeder=DistributionFeeder.example(),
            name="Branch-DistBus1",
        )
        bus2 = DistributionBus(
            voltage_type="line-to-ground",
            phases=[Phase.A, Phase.B, Phase.C],
            rated_voltage=Voltage(400, "volt"),
            substation=DistributionSubstation.example(),
            feeder=DistributionFeeder.example(),
            name="Branch-DistBus2",
        )
        return SequenceImpedanceBranch(
            buses=[bus1, bus2],
            length=Distance(130.2, "meter"),
            phases=[Phase.A, Phase.B, Phase.C],
            substation=DistributionSubstation.example(),
            feeder=DistributionFeeder.example(),
            name="DistBranch1",
            equipment=SequenceImpedanceBranchEquipment.example(),
        )
