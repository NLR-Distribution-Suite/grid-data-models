"""This module contains interface for distribution system capacitor."""

from typing import Annotated

from pydantic import Field, model_validator

from gdm.systems.distribution.controllers.distribution_inverter_controller import (
    InverterController,
)
from gdm.quantities import Voltage, ActivePower, ReactivePower, Irradiance
from gdm.systems.distribution.components.distribution_feeder import DistributionFeeder
from gdm.systems.distribution.equipment.inverter_equipment import InverterEquipment
from gdm.systems.distribution.components.base.distribution_component_base import (
    InServiceDistributionComponentBase,
)
from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.systems.distribution.equipment.solar_equipment import SolarEquipment
from gdm.systems.distribution.components.distribution_substation import (
    DistributionSubstation,
)
from gdm.systems.distribution.enums import ControllerSupport
from gdm.systems.distribution.enums import Phase


class DistributionSolar(InServiceDistributionComponentBase):
    """Data model for Solar PV system in distribution system models."""

    bus: Annotated[
        DistributionBus,
        Field(
            ...,
            description="Distribution bus to which this solar array is connected to.",
        ),
    ]
    phases: Annotated[
        list[Phase],
        Field(
            ...,
            description=(
                "List of phases at which this solar array is connected to in the same order."
            ),
        ),
    ]
    irradiance: Annotated[
        Irradiance,
        Field(..., description="Irradiance incident on the PV array.", ge=0),
    ]
    active_power: Annotated[
        ActivePower,
        Field(..., description="Active power output of the inverter.", ge=0),
    ]
    reactive_power: Annotated[
        ReactivePower,
        Field(..., description="Reactive power output of the inverter."),
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
        Field(..., description="Inverter equipment for the Distribution Solar PV system."),
    ]
    equipment: Annotated[SolarEquipment, Field(..., description="Solar PV model.")]

    @model_validator(mode="after")
    def validate_controller_types(self) -> "DistributionSolar":
        valid_controller_types = [
            ControllerSupport.SOLAR_ONLY,
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
        instances: list["DistributionSolar"],
        bus: DistributionBus,
        name: str,
        split_phase_mapping: dict[str, set[Phase]],
    ) -> "DistributionSolar":
        phases = set()
        for solar in instances:
            if {Phase.S1, Phase.S2} & set(solar.phases):
                parent_phase = split_phase_mapping[solar.name]
                phases = phases.union(set(parent_phase))
            else:
                phases = phases.union(set(solar.phases))

        return DistributionSolar(
            name=name,
            bus=bus,
            phases=list(phases),
            equipment=SolarEquipment(
                name=f"{name}_solar_equipment",
                rated_power=sum(inst.equipment.rated_power for inst in instances),
                resistance=1
                / sum(
                    (1 / inst.equipment.resistance if inst.equipment.resistance else 0)
                    for inst in instances
                ),
                reactance=1
                / sum(
                    (1 / inst.equipment.reactance if inst.equipment.reactance else 0)
                    for inst in instances
                ),
                rated_voltage=bus.rated_voltage,
                voltage_type=bus.voltage_type,
            ),
            inverter=InverterEquipment(
                rated_apparent_power=sum(inst.inverter.rated_apparent_power for inst in instances)
                / len(instances),
                rise_limit=None,
                fall_limit=None,
                eff_curve=None,
                dc_to_ac_efficiency=sum(inst.inverter.dc_to_ac_efficiency for inst in instances)
                / len(instances),
                cutin_percent=sum(inst.inverter.cutin_percent for inst in instances)
                / len(instances),
                cutout_percent=sum(inst.inverter.cutout_percent for inst in instances)
                / len(instances),
            ),
            controller=None,
            irradiance=sum(inst.irradiance * inst.equipment.rated_power for inst in instances)
            / sum(inst.equipment.rated_power for inst in instances),
            active_power=sum(inst.active_power for inst in instances),
            reactive_power=sum(inst.reactive_power for inst in instances),
        )

    @classmethod
    def example(cls) -> "DistributionSolar":
        """Example for a Solar PV"""
        return DistributionSolar(
            name="pv1",
            bus=DistributionBus(
                voltage_type="line-to-ground",
                name="Solar-DistBus1",
                rated_voltage=Voltage(400, "volt"),
                phases=[Phase.A, Phase.B, Phase.C],
                substation=DistributionSubstation.example(),
                feeder=DistributionFeeder.example(),
            ),
            substation=DistributionSubstation.example(),
            feeder=DistributionFeeder.example(),
            phases=[Phase.A, Phase.B, Phase.C],
            equipment=SolarEquipment.example(),
            inverter=InverterEquipment.example(),
            controller=InverterController.example(),
            active_power=ActivePower(1000, "watt"),
            reactive_power=ReactivePower(1000, "watt"),
            irradiance=Irradiance(1000, "watt/m^2"),
        )
