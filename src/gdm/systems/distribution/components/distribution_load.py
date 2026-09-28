"""This module contains interface for distribution load."""

from collections import defaultdict
from typing import Annotated, Self

from pydantic import model_validator, Field

from gdm.systems.distribution.enums import Phase
from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.systems.distribution.components.base.distribution_component_base import (
    InServiceDistributionComponentBase,
)
from gdm.systems.distribution.components.distribution_feeder import DistributionFeeder
from gdm.systems.distribution.components.distribution_substation import (
    DistributionSubstation,
)
from gdm.systems.distribution.equipment.phase_load_equipment import PhaseLoadEquipment
from gdm.quantities import Voltage
from gdm.systems.distribution.equipment.load_equipment import LoadEquipment


class DistributionLoad(InServiceDistributionComponentBase):
    """Data model for distribution load."""

    bus: Annotated[
        DistributionBus,
        Field(
            ...,
            description="Distribution bus to which this load is connected to.",
        ),
    ]
    phases: Annotated[
        list[Phase],
        Field(..., description="Phases to which this load is connected to."),
    ]
    equipment: Annotated[LoadEquipment, Field(..., description="Load model.")]

    @classmethod
    def aggregate(
        cls,
        instances: list["DistributionLoad"],
        bus: DistributionBus,
        name: str,
        split_phase_mapping: dict[str, set[Phase]],
    ) -> Self:
        phase_loads = defaultdict(list)
        for load in instances:
            if {Phase.S1, Phase.S2} & set(load.phases):
                parent_phase = split_phase_mapping[load.name]
                split_load = PhaseLoadEquipment.split(
                    PhaseLoadEquipment.aggregate(load.equipment.phase_loads, name=""),
                    len(parent_phase),
                )
                for phase in parent_phase:
                    phase_loads[phase].append(split_load)
                continue
            for phase, phase_load in zip(load.phases, load.equipment.phase_loads):
                phase_loads[phase].append(phase_load)

        return DistributionLoad(
            name=name,
            bus=bus,
            phases=list(phase_loads.keys()),
            equipment=LoadEquipment(
                name=f"{name}_load_equipment",
                phase_loads=[
                    PhaseLoadEquipment.aggregate(loads, name="") for loads in phase_loads.values()
                ],
                connection_type=set([item.equipment.connection_type for item in instances]).pop(),
            ),
        )

    @model_validator(mode="after")
    def validate_fields(self) -> "DistributionLoad":
        """Custom validator for fields in distribution load."""
        if not set(self.phases).issubset(set(self.bus.phases)):
            msg = f"Loads phases {self.phases=} must be subset of bus phases. {self.bus.phases}"
            raise ValueError(msg)

        if len(self.phases) != len(self.equipment.phase_loads):
            msg = (
                f"Number of phases {self.phases=} did not "
                f"match number of phase loads {self.equipment.phase_loads=}"
            )
            raise ValueError(msg)
        return self

    @classmethod
    def example(cls) -> "DistributionLoad":
        """Example for distribution load."""
        return DistributionLoad(
            name="DistributionLoad1",
            bus=DistributionBus(
                voltage_type="line-to-ground",
                name="Load-DistBus1",
                phases=[Phase.A, Phase.B, Phase.C],
                substation=DistributionSubstation.example(),
                feeder=DistributionFeeder.example(),
                rated_voltage=Voltage(0.4, "kilovolt"),
            ),
            substation=DistributionSubstation.example(),
            feeder=DistributionFeeder.example(),
            phases=[Phase.A, Phase.B, Phase.C],
            equipment=LoadEquipment.example(),
        )
