"""This module contains interface for distribution system capacitor."""

from typing import Annotated

from pydantic import Field, model_validator

from gdm.systems.distribution.components.distribution_feeder import DistributionFeeder
from gdm.systems.distribution.equipment.inverter_equipment import InverterEquipment
from gdm.systems.distribution.controllers.distribution_inverter_controller import (
    PeakShavingBaseLoadingControlSetting,
    VoltVarControlSetting,
    InverterController,
)
from gdm.systems.distribution.components.base.distribution_component_base import (
    InServiceDistributionComponentBase,
)
from gdm.systems.distribution.equipment.battery_equipment import BatteryEquipment
from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.quantities import Voltage, ActivePower, ReactivePower
from gdm.systems.distribution.components.distribution_substation import (
    DistributionSubstation,
)
from gdm.systems.distribution.enums import ControllerSupport
from gdm.systems.distribution.enums import Phase


class DistributionBattery(InServiceDistributionComponentBase):
    """Data model for battery system in distribution system models."""

    bus: Annotated[
        DistributionBus,
        Field(
            ...,
            description="Distribution bus to which this battery is connected to.",
        ),
    ]
    phases: Annotated[
        list[Phase],
        Field(
            ...,
            description=(
                "List of phases at which this battery is connected to in the same order."
            ),
        ),
    ]
    active_power: Annotated[
        ActivePower,
        Field(..., description="Current active power output of the battery."),
    ]
    reactive_power: Annotated[
        ReactivePower,
        Field(..., description="Current reactive power output of the battery."),
    ]
    controller: Annotated[
        InverterController | None,
        Field(
            None,
            description="Controller settings to control output of the inverter",
        ),
    ]

    inverter: Annotated[
        InverterEquipment,
        Field(..., description="Inverter equipment for the distribution battery system."),
    ]

    equipment: Annotated[BatteryEquipment, Field(..., description="Battery model.")]

    @model_validator(mode="after")
    def validate_controller_types(self) -> "DistributionBattery":
        valid_controller_types = [
            ControllerSupport.BATTERY_ONLY,
            ControllerSupport.BATTERY_AND_SOLAR,
        ]
        if self.controller is not None:
            if self.controller.active_power_control is not None:
                if self.controller.active_power_control.supported_by not in valid_controller_types:
                    raise ValueError(
                        f"Controller type '{self.controller.active_power_control.supported_by}' is not supported by DistributionSolar. Supported Controller types: {valid_controller_types}"
                    )

            if self.controller.reactive_power_control is not None:
                if (
                    self.controller.reactive_power_control.supported_by
                    not in valid_controller_types
                ):
                    raise ValueError(
                        f"Controller type '{self.controller.reactive_power_control.supported_by}' is not supported by DistributionSolar. Supported Controller types: {valid_controller_types}"
                    )

        return self

    @classmethod
    def aggregate(
        cls,
        instances: list["DistributionBattery"],
        bus: DistributionBus,
        name: str,
        split_phase_mapping: dict[str, set[Phase]],
    ) -> "DistributionBattery":
        """
        Aggregates multiple DistributionBattery instances into a single instance.

        This method combines the properties of multiple DistributionBattery
        instances connected to the same bus into a single DistributionBattery
        instance. It calculates the aggregate phases, equipment ratings, and
        efficiencies based on the provided instances.

        Args:
            instances (list[DistributionBattery]): List of DistributionBattery
                instances to be aggregated.
            bus (DistributionBus): The bus to which the aggregated battery is
                connected.
            name (str): The name for the aggregated DistributionBattery.
            split_phase_mapping (dict[str, set[Phase]]): Mapping of battery names
                to their respective split phases.

        Returns:
            DistributionBattery: A new DistributionBattery instance representing
            the aggregate of the provided instances.
        """
        phases = set()
        for battery in instances:
            if {Phase.S1, Phase.S2} & set(battery.phases):
                parent_phase = split_phase_mapping[battery.name]
                phases = phases.union(set(parent_phase))
            else:
                phases = phases.union(set(battery.phases))

        return DistributionBattery(
            name=name,
            bus=bus,
            phases=list(phases),
            equipment=BatteryEquipment(
                name=f"{name}_battery_equipment",
                rated_energy=sum(inst.equipment.rated_energy for inst in instances),
                rated_power=sum(inst.equipment.rated_power for inst in instances),
                charging_efficiency=sum(inst.equipment.charging_efficiency for inst in instances)
                / len(instances),
                discharging_efficiency=sum(
                    inst.equipment.discharging_efficiency for inst in instances
                )
                / len(instances),
                idling_efficiency=sum(inst.equipment.idling_efficiency for inst in instances)
                / len(instances),
                rated_voltage=bus.rated_voltage,
                voltage_type=bus.voltage_type,
            ),
            inverter=InverterEquipment(
                rated_apparent_power=sum(inst.inverter.rated_apparent_power for inst in instances),
                rise_limit=None,
                fall_limit=None,
                eff_curve=None,
                cutin_percent=sum(inst.inverter.cutin_percent for inst in instances)
                / len(instances),
                cutout_percent=sum(inst.inverter.cutout_percent for inst in instances)
                / len(instances),
                dc_to_ac_efficiency=sum(inst.inverter.dc_to_ac_efficiency for inst in instances)
                / len(instances),
            ),
            reactive_power=sum(inst.reactive_power for inst in instances),
            active_power=sum(inst.active_power for inst in instances),
            controller=None,
        )

    @classmethod
    def example(cls) -> "DistributionBattery":
        """Example of a distribution battery system."""
        return DistributionBattery(
            name="battery1",
            bus=DistributionBus(
                voltage_type="line-to-ground",
                name="Battery-DistBus1",
                rated_voltage=Voltage(400, "volt"),
                phases=[Phase.A, Phase.B, Phase.C],
                substation=DistributionSubstation.example(),
                feeder=DistributionFeeder.example(),
            ),
            substation=DistributionSubstation.example(),
            feeder=DistributionFeeder.example(),
            phases=[Phase.A, Phase.B, Phase.C],
            equipment=BatteryEquipment.example(),
            inverter=InverterEquipment.example(),
            reactive_power=ReactivePower(1000, "watt"),
            active_power=ActivePower(1000, "watt"),
            controller=InverterController(
                name="inv1",
                active_power_control=PeakShavingBaseLoadingControlSetting.example(),
                reactive_power_control=VoltVarControlSetting.example(),
                prioritize_active_power=False,
                night_mode=True,
            ),
        )
