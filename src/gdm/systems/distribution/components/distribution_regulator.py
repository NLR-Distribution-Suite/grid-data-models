"""This module contains distribution regulator."""

from typing import Annotated

from pydantic import Field, model_validator

from gdm.systems.distribution.components.base.distribution_transformer_base import (
    DistributionTransformerBase,
)
from gdm.systems.distribution.components.distribution_feeder import DistributionFeeder
from gdm.systems.distribution.components.distribution_substation import DistributionSubstation
from gdm.systems.distribution.controllers.distribution_regulator_controller import (
    RegulatorController,
)
from gdm.systems.distribution.equipment.distribution_transformer_equipment import (
    DistributionTransformerEquipment,
)
from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.systems.distribution.enums import Phase, VoltageTypes
from gdm.quantities import Voltage


class DistributionRegulator(DistributionTransformerBase):
    controllers: Annotated[
        list[RegulatorController],
        Field(
            ...,
            description="The regulators that are used to control voltage on each phase of the transformer",
        ),
    ]

    @model_validator(mode="after")
    def validate_fields(self) -> "DistributionRegulator":
        """Custom validator for voltage regulator."""
        for winding in self.equipment.windings:
            if len(winding.tap_positions) != len(self.controllers):
                msg = (
                    f"Number of tap positions {winding.tap_positions=} "
                    f"should be equal to the number of controllers {self.controllers=}."
                )
                raise ValueError(msg)
        return self

    @classmethod
    def example(cls) -> "DistributionRegulator":
        """Example for Voltage Regulator"""
        return DistributionRegulator(
            name="DistributionRegulator1",
            buses=[
                DistributionBus(
                    voltage_type=VoltageTypes.LINE_TO_LINE,
                    name="Regulator-DistBus1",
                    rated_voltage=Voltage(12.47, "kilovolt"),
                    substation=DistributionSubstation.example(),
                    feeder=DistributionFeeder.example(),
                    phases=[Phase.A, Phase.B, Phase.C],
                ),
                DistributionBus(
                    voltage_type=VoltageTypes.LINE_TO_LINE,
                    name="Regulator-DistBus2",
                    rated_voltage=Voltage(0.4, "kilovolt"),
                    substation=DistributionSubstation.example(),
                    feeder=DistributionFeeder.example(),
                    phases=[Phase.A, Phase.B, Phase.C],
                ),
            ],
            winding_phases=[[Phase.A, Phase.B, Phase.C], [Phase.A, Phase.B, Phase.C]],
            tap_positions=[[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]],
            equipment=DistributionTransformerEquipment.example(),
            controllers=[
                RegulatorController.example(),
                RegulatorController.example(),
                RegulatorController.example(),
            ],
        )
