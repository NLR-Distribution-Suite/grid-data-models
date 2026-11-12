"""Distribution generator component."""

from enum import Enum
from typing import Annotated

from pydantic import Field

from gdm.quantities import ActivePower, ReactivePower
from gdm.systems.distribution.components.base.distribution_component_base import (
    InServiceDistributionComponentBase,
)
from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.systems.distribution.enums import Phase
from gdm.systems.distribution.equipment.generator_equipment import GeneratorEquipment


class GeneratorOperatingMode(str, Enum):
    """Steady-state generator power-flow model."""

    CONSTANT_PQ = "constant-pq"
    CONSTANT_IMPEDANCE = "constant-impedance"
    CONSTANT_PV = "constant-pv"
    CONSTANT_P_FIXED_Q = "constant-p-fixed-q"
    CONSTANT_P_FIXED_REACTANCE = "constant-p-fixed-reactance"
    APPROXIMATE_INVERTER = "approximate-inverter"


class DistributionGenerator(InServiceDistributionComponentBase):
    """A generator connected to a distribution bus."""

    bus: Annotated[DistributionBus, Field(..., description="Generator terminal bus.")]
    phases: Annotated[list[Phase], Field(..., description="Connected phases in conductor order.")]
    equipment: Annotated[GeneratorEquipment, Field(..., description="Generator equipment.")]
    active_power: Annotated[ActivePower, Field(..., description="Active power setpoint.")]
    reactive_power: Annotated[ReactivePower, Field(..., description="Reactive power setpoint.")]
    operating_mode: Annotated[GeneratorOperatingMode, Field(..., description="Power-flow model.")]
    voltage_setpoint_pu: Annotated[float, Field(..., description="Voltage setpoint.", gt=0)]
    min_voltage_pu: Annotated[float, Field(..., description="Minimum model voltage.", gt=0)]
    max_voltage_pu: Annotated[float, Field(..., description="Maximum model voltage.", gt=0)]
    min_reactive_power: Annotated[ReactivePower, Field(..., description="Minimum reactive power.")]
    max_reactive_power: Annotated[ReactivePower, Field(..., description="Maximum reactive power.")]

    @classmethod
    def example(cls) -> "DistributionGenerator":
        return cls(
            name="generator",
            bus=DistributionBus.example(),
            phases=[Phase.A, Phase.B, Phase.C],
            equipment=GeneratorEquipment.example(),
            active_power=ActivePower(500, "kW"),
            reactive_power=ReactivePower(100, "kvar"),
            operating_mode=GeneratorOperatingMode.CONSTANT_PQ,
            voltage_setpoint_pu=1.0,
            min_voltage_pu=0.9,
            max_voltage_pu=1.1,
            min_reactive_power=ReactivePower(-500, "kvar"),
            max_reactive_power=ReactivePower(500, "kvar"),
        )
