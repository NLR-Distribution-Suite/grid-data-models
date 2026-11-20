"""Distribution generator component."""

from enum import Enum
from typing import Annotated, Self
from uuid import uuid4

from pydantic import Field

from gdm.quantities import ActivePower, ReactivePower
from gdm.systems.distribution.components.base.distribution_component_base import (
    InServiceDistributionComponentBase,
    _in_service_components,
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

    def _aggregation_phases(self, split_phase_mapping: dict[str, set[Phase]]) -> set[Phase]:
        if {Phase.S1, Phase.S2} & set(self.phases):
            return set(split_phase_mapping[self.name])
        return set(self.phases)

    def _aggregation_key(self, split_phase_mapping: dict[str, set[Phase]]) -> tuple:
        equipment = self.equipment
        return (
            frozenset(self._aggregation_phases(split_phase_mapping)),
            self.operating_mode,
            self.voltage_setpoint_pu,
            self.min_voltage_pu,
            self.max_voltage_pu,
            equipment.rated_voltage.to("volt").magnitude,
            equipment.connection_type,
            equipment.synchronous_reactance_pu,
            equipment.transient_reactance_pu,
            equipment.subtransient_reactance_pu,
            equipment.inertia_seconds,
            equipment.damping,
        )

    @classmethod
    def _group_for_aggregation(
        cls, instances: list[Self], split_phase_mapping: dict[str, set[Phase]]
    ) -> list[list[Self]]:
        groups: dict[tuple, list[Self]] = {}
        for instance in instances:
            groups.setdefault(instance._aggregation_key(split_phase_mapping), []).append(instance)
        return list(groups.values())

    @classmethod
    def aggregate(
        cls,
        instances: list[Self],
        bus: DistributionBus,
        name: str,
        split_phase_mapping: dict[str, set[Phase]],
    ) -> Self:
        """Combine compatible in-service generators at a bus.

        Phases, operating controls, and machine parameters must match; ratings,
        power setpoints, and reactive power limits are summed.
        """
        instances = _in_service_components(instances)
        groups = cls._group_for_aggregation(instances, split_phase_mapping)
        if len(groups) != 1:
            raise ValueError("Cannot aggregate generators with incompatible settings.")
        first = instances[0]
        phases = first._aggregation_phases(split_phase_mapping)
        if not phases.issubset(bus.phases):
            raise ValueError("Generator phases are incompatible with the target bus.")
        equipment = first.equipment.model_copy(
            update={
                "uuid": uuid4(),
                "name": f"{name}_generator_equipment",
                "rated_apparent_power": sum(
                    instance.equipment.rated_apparent_power for instance in instances
                ),
                "rated_voltage": bus.rated_voltage,
            }
        )
        return cls(
            name=name,
            bus=bus,
            phases=sorted(phases, key=lambda phase: phase.value),
            equipment=equipment,
            active_power=sum(instance.active_power for instance in instances),
            reactive_power=sum(instance.reactive_power for instance in instances),
            operating_mode=first.operating_mode,
            voltage_setpoint_pu=first.voltage_setpoint_pu,
            min_voltage_pu=first.min_voltage_pu,
            max_voltage_pu=first.max_voltage_pu,
            min_reactive_power=sum(instance.min_reactive_power for instance in instances),
            max_reactive_power=sum(instance.max_reactive_power for instance in instances),
        )

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
