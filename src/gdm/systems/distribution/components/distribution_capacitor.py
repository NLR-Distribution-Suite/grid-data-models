"""This module contains interface for distribution system capacitor."""

from collections import defaultdict
from typing import Annotated

from pydantic import Field, computed_field, model_validator

from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.systems.distribution.equipment.capacitor_equipment import CapacitorEquipment
from gdm.systems.distribution.components.base.distribution_component_base import (
    InServiceDistributionComponentBase,
)
from gdm.systems.distribution.components.distribution_feeder import DistributionFeeder
from gdm.systems.distribution.components.distribution_substation import DistributionSubstation
from gdm.systems.distribution.equipment.phase_capacitor_equipment import PhaseCapacitorEquipment
from gdm.quantities import Voltage
from gdm.systems.distribution.enums import Phase
from gdm.systems.distribution.controllers.distribution_capacitor_controller import (
    VoltageCapacitorController,
)
from gdm.systems.distribution.controllers.base.capacitor_controller_base import (
    CapacitorControllerBase,
)


class DistributionCapacitor(InServiceDistributionComponentBase):
    """Data model for capacitor present in distribution system models."""

    bus: Annotated[
        DistributionBus,
        Field(
            ...,
            description="Distribution bus to which this capacitor is connected to.",
        ),
    ]
    phases: Annotated[
        list[Phase],
        Field(
            ...,
            description=(
                "List of phases that have capacitor controllers. Phase order should be in the same order as the controllers."
            ),
        ),
    ]
    controllers: Annotated[
        list[CapacitorControllerBase],
        Field(
            [],
            description="List of the controllers which are used for each phase in order.",
        ),
    ]

    equipment: Annotated[CapacitorEquipment, Field(..., description="Capacitor model.")]
    state: Annotated[
        list[bool],
        Field(
            ...,
            description="List of boolean states indicating whether each bank is on (True) or off (False).",
        ),
    ]

    @computed_field  # type: ignore[prop-decorator]
    @property
    def num_banks(self) -> int:
        """Number of banks in the capacitor."""
        return len(self.state)

    @classmethod
    def aggregate(
        cls,
        instances: list["DistributionCapacitor"],
        bus: DistributionBus,
        name: str,
        split_phase_mapping: dict[str, set[Phase]],
    ) -> "DistributionCapacitor":
        phase_caps = defaultdict(list)
        for cap in instances:
            if {Phase.S1, Phase.S2} & set(cap.phases):
                parent_phase = split_phase_mapping[cap.uuid]
                split_cap = PhaseCapacitorEquipment.split(
                    PhaseCapacitorEquipment.aggregate(cap.equipment.phase_capacitors, name=""),
                    len(parent_phase),
                )
                for phase in parent_phase:
                    phase_caps[phase].append(split_cap)
                continue
            for phase, phase_load in zip(cap.phases, cap.equipment.phase_capacitors):
                phase_caps[phase].append(phase_load)

        return DistributionCapacitor(
            name=name,
            bus=bus,
            phases=list(phase_caps.keys()),
            equipment=CapacitorEquipment(
                name=f"{name}_capacitor_equipment",
                phase_capacitors=[
                    PhaseCapacitorEquipment.aggregate(caps, name="")
                    for caps in phase_caps.values()
                ],
                connection_type=set([item.equipment.connection_type for item in instances]).pop(),
                rated_voltage=bus.rated_voltage,
                voltage_type=bus.voltage_type,
            ),
            state=[True] * len(phase_caps),
        )

    @model_validator(mode="after")
    def validate_fields(self) -> "DistributionCapacitor":
        """Custom validator for fields."""
        if not set(self.phases).issubset(set(self.bus.phases)):
            msg = (
                f"Phase capacitors phases ({self.phases}) should be subset of bus phases"
                f" ({self.bus.phases}) to which it is connected to."
            )
            raise ValueError(msg)
        if len(self.phases) != len(self.equipment.phase_capacitors):
            msg = (
                f"Length of phase capacitors {self.equipment.phase_capacitors=} "
                f"did not match length of phases {self.phases=}"
            )
        if len(self.equipment.phase_capacitors) != len(self.controllers):
            msg = (
                f"Number of controllers ({self.controllers=}) "
                f"did not match number of phase capacitors {self.equipment.phase_capacitors=}"
            )
        return self

    @classmethod
    def example(cls) -> "DistributionCapacitor":
        """Example for distribution capacitor."""
        return DistributionCapacitor(
            name="Capacitor1",
            bus=DistributionBus(
                voltage_type="line-to-ground",
                name="Capacitor-DistBus1",
                rated_voltage=Voltage(400, "volt"),
                phases=[Phase.A, Phase.B, Phase.C],
                substation=DistributionSubstation.example(),
                feeder=DistributionFeeder.example(),
            ),
            substation=DistributionSubstation.example(),
            feeder=DistributionFeeder.example(),
            phases=[Phase.A, Phase.B, Phase.C],
            equipment=CapacitorEquipment.example(),
            state=[True, True, True],
            controllers=[
                VoltageCapacitorController.example(),
            ],
        )
