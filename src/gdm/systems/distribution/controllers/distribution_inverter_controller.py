"""This module contains interface for distribution inverter controllers."""

from typing import Annotated, Literal
from datetime import time

from infrasys import Component
from pydantic import Field


from gdm.systems.distribution.controllers.base.inverter_controller_base import (
    ReactivePowerInverterControllerBase,
    ActivePowerInverterControllerBase,
)
from gdm.systems.distribution.market.tariff import DistributionTariff
from gdm.quantities import ActivePower, ActivePowerOverTime
from gdm.systems.distribution.enums import ControllerSupport
from gdm.systems.distribution.common.curve import Curve


class PowerfactorControlSetting(ReactivePowerInverterControllerBase):
    """
    Control settings for the  Inverter Controller to represent power factor control.
    Works with both battery and solar systems. Controls reactive power output of the
    connected inverter
    """

    power_factor: Annotated[
        float, Field(ge=-1, le=1, description="The power factor used for the controller.")
    ]
    supported_by: Literal[
        ControllerSupport.BATTERY_AND_SOLAR
    ] = ControllerSupport.BATTERY_AND_SOLAR

    @classmethod
    def example(cls) -> "PowerfactorControlSetting":
        "Example of a Power Factor setting for the Inverter reactive power control option"
        return PowerfactorControlSetting(
            power_factor=0.95,
        )


class VoltVarControlSetting(ReactivePowerInverterControllerBase):
    """
    Control settings for the Inverter Controller to represent volt / var control settings.
    Works with both battery and solar systems. Controls reactive power output of the
    connected inverter
    """

    volt_var_curve: Annotated[
        Curve, Field(..., description="The volt-var curve that is being applied.")
    ]
    var_follow: Annotated[
        bool,
        Field(
            ...,
            description="""Set to false if you want inverter reactive power
                        generation absorption to respect inverter status""",
        ),
    ]
    supported_by: Literal[
        ControllerSupport.BATTERY_AND_SOLAR
    ] = ControllerSupport.BATTERY_AND_SOLAR

    @classmethod
    def example(cls) -> "VoltVarControlSetting":
        "Example of a Volt-Var Inverter Controller"
        return VoltVarControlSetting(
            volt_var_curve=Curve.example(),
            var_follow=False,
        )


class VoltWattControlSetting(ActivePowerInverterControllerBase):
    """
    Control settings for the Inverter Controller to represent volt / watt control settings.
    Works with both battery and solar systems. Controls active power output of the
    connected inverter
    """

    volt_watt_curve: Annotated[
        Curve, Field(..., description="The volt-watt curve that is being applied.")
    ]
    supported_by: Literal[
        ControllerSupport.BATTERY_AND_SOLAR
    ] = ControllerSupport.BATTERY_AND_SOLAR

    @classmethod
    def example(cls) -> "VoltWattControlSetting":
        "Example of a Volt-Watt Inverter Controller"
        return VoltWattControlSetting(
            volt_watt_curve=Curve(curve_x=[0.5, 1.06, 1.1, 1.5], curve_y=[1.0, 1.0, 0.0, 0.0]),
        )


class PeakShavingBaseLoadingControlSetting(ActivePowerInverterControllerBase):
    """
    Control settings for the Inverter Controller to represent peak shaving / base loading
    control settings. Works with battery systems only. Controls active power output of the
    connected inverter. If the loading on the controlled element exceeds peak_shaving_target,
    the battery discharges to shave off peak load. If the loading drops below the
    base_loading_target, the battery charges to maintain minimum loading.
    """

    supported_by: Literal[ControllerSupport.BATTERY_ONLY] = ControllerSupport.BATTERY_ONLY
    peak_shaving_target: Annotated[ActivePower, Field(..., description="The peak shaving target.")]
    base_loading_target: Annotated[ActivePower, Field(..., description="The base loading target.")]

    @classmethod
    def example(cls) -> "PeakShavingBaseLoadingControlSetting":
        "Example of a battery peak shaving base loading controller"
        return PeakShavingBaseLoadingControlSetting(
            peak_shaving_target=ActivePower(1000, "watt"),
            base_loading_target=ActivePower(2000, "watt"),
        )


class CapacityFirmingControlSetting(ActivePowerInverterControllerBase):
    """
    Control settings for the Inverter Controller to represent capacity firming
    control settings. Works with battery systems only. Controls active power output of the
    connected inverter
    """

    supported_by: Literal[ControllerSupport.BATTERY_ONLY] = ControllerSupport.BATTERY_ONLY
    max_active_power_roc: Annotated[
        ActivePowerOverTime,
        Field(
            ...,
            description="Maximum allowable rate of charge for active power on the controlled bus.",
        ),
    ]
    min_active_power_roc: Annotated[
        ActivePowerOverTime,
        Field(
            ...,
            description="Minimum allowable rate of charge for active power on the controlled bus.",
        ),
    ]

    @classmethod
    def example(cls) -> "CapacityFirmingControlSetting":
        "Example of a battery capacity firming controller"
        return CapacityFirmingControlSetting(
            max_active_power_roc=ActivePowerOverTime(1000, "kilowatt/second"),
            min_active_power_roc=ActivePowerOverTime(1000, "kilowatt/second"),
        )


class TimeBasedControlSetting(ActivePowerInverterControllerBase):
    """
    Control settings for the Inverter Controller to represent time based charge / discharge
    control settings. Works with battery systems only. Controls active power output of the
    connected inverter
    """

    supported_by: Literal[ControllerSupport.BATTERY_ONLY] = ControllerSupport.BATTERY_ONLY
    charging_start_time: Annotated[
        time, Field(..., description="The time at which the battery starts charging.")
    ]
    charging_end_time: Annotated[
        time, Field(..., description="The time at which the battery stops charging.")
    ]
    discharging_start_time: Annotated[
        time, Field(..., description="The time at which the battery starts discharging.")
    ]
    discharging_end_time: Annotated[
        time, Field(..., description="The time at which the battery stops discharging.")
    ]
    charging_power: Annotated[
        ActivePower, Field(..., description="The power to charge the battery.")
    ]
    discharging_power: Annotated[
        ActivePower, Field(..., description="The power to discharge the battery.")
    ]

    @classmethod
    def example(cls) -> "TimeBasedControlSetting":
        "Example of a battery capacity firming controller"
        return TimeBasedControlSetting(
            charging_start_time=time(hour=10, minute=0),
            charging_end_time=time(hour=11, minute=0),
            discharging_start_time=time(hour=21, minute=0),
            discharging_end_time=time(hour=22, minute=0),
            charging_power=ActivePower(1000, "watt"),
            discharging_power=ActivePower(1000, "watt"),
        )


class SelfConsumptionControlSetting(ActivePowerInverterControllerBase):
    """
    Control settings for the Inverter Controller to represent self comsumption
    control settings. Works with battery systems only. Controls active power output of the
    connected inverter
    """

    supported_by: Literal[ControllerSupport.BATTERY_ONLY] = ControllerSupport.BATTERY_ONLY

    @classmethod
    def example(cls) -> "SelfConsumptionControlSetting":
        "Example of a battery self consumption controller"
        return SelfConsumptionControlSetting()


class TimeOfUseControlSetting(ActivePowerInverterControllerBase):
    """
    Control settings for the Inverter Controller to represent time of use
    control settings. Works with battery systems only. Controls active power output of the
    connected inverter
    """

    supported_by: Literal[ControllerSupport.BATTERY_ONLY] = ControllerSupport.BATTERY_ONLY
    tarriff: DistributionTariff
    charging_power: Annotated[
        ActivePower, Field(..., description="The power to charge the battery after TOU window.")
    ]

    @classmethod
    def example(cls) -> "TimeOfUseControlSetting":
        "Example of a battery time of use controller"
        return TimeOfUseControlSetting(
            charging_power=ActivePower(1000, "watt"),
            tarriff=DistributionTariff.example(),
        )


class DemandChargeControlSetting(ActivePowerInverterControllerBase):
    """
    Control settings for the Inverter Controller to represent demand charge focused
    control settings. Works with battery systems only. Controls active power output of the
    connected inverter
    """

    supported_by: Literal[ControllerSupport.BATTERY_ONLY] = ControllerSupport.BATTERY_ONLY
    tarriff: DistributionTariff
    charging_power: Annotated[
        ActivePower,
        Field(..., description="The power to charge the battery after demand change window."),
    ]

    @classmethod
    def example(cls) -> "DemandChargeControlSetting":
        "Example of a battery demand charge controller"
        return DemandChargeControlSetting(
            charging_power=ActivePower(1000, "watt"),
            tarriff=DistributionTariff.example(),
        )


class InverterController(Component):
    """Inverter contoller represent the complete control settings for a given
    InverterEquipment. This model may be used with an instance of DistributionSolar,
    DistributionBattery or any other model that has an inverter.
    """

    name: Annotated[str, Field("", description="Name of the inverter controller.")]

    active_power_control: Annotated[
        ActivePowerInverterControllerBase | None,
        Field(
            None,
            description="Controller settings to control active power output of the inverter",
        ),
    ]

    reactive_power_control: Annotated[
        ReactivePowerInverterControllerBase | None,
        Field(
            None,
            description="Controller settings to control reactive power output of the inverter",
        ),
    ]

    prioritize_active_power: Annotated[
        bool, Field(..., description="If True, the controller tries to prioritize active power.")
    ]

    night_mode: Annotated[
        bool,
        Field(
            ...,
            description="If True, the controller controls reactive power even when there is no active power.",
        ),
    ]

    @classmethod
    def example(cls) -> "InverterController":
        "Example of a Volt-Watt Inverter Controller"
        return InverterController(
            name="inv1",
            active_power_control=VoltWattControlSetting.example(),
            reactive_power_control=VoltVarControlSetting.example(),
            prioritize_active_power=False,
            night_mode=True,
        )
