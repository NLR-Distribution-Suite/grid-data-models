"""Equipment ratings and dynamic parameters for a distribution generator."""

from typing import Annotated

from infrasys import Component
from pydantic import Field

from gdm.quantities import ApparentPower, Voltage
from gdm.systems.distribution.enums import ConnectionType


class GeneratorEquipment(Component):
    """Nameplate and machine parameters of a generator."""

    rated_apparent_power: Annotated[
        ApparentPower, Field(..., description="Generator apparent power rating.", gt=0)
    ]
    rated_voltage: Annotated[Voltage, Field(..., description="Rated terminal voltage.", gt=0)]
    connection_type: Annotated[ConnectionType, Field(..., description="Winding connection.")]
    synchronous_reactance_pu: Annotated[
        float, Field(..., description="Synchronous reactance in per unit.", ge=0)
    ]
    transient_reactance_pu: Annotated[
        float, Field(..., description="Transient reactance in per unit.", ge=0)
    ]
    subtransient_reactance_pu: Annotated[
        float, Field(..., description="Subtransient reactance in per unit.", ge=0)
    ]
    inertia_seconds: Annotated[float, Field(..., description="Inertia constant in seconds.", ge=0)]
    damping: Annotated[float, Field(..., description="Per-unit damping coefficient.", ge=0)]

    @classmethod
    def example(cls) -> "GeneratorEquipment":
        return cls(
            name="generator-equipment",
            rated_apparent_power=ApparentPower(1000, "kVA"),
            rated_voltage=Voltage(12.47, "kV"),
            connection_type=ConnectionType.STAR,
            synchronous_reactance_pu=1.0,
            transient_reactance_pu=0.28,
            subtransient_reactance_pu=0.2,
            inertia_seconds=1.0,
            damping=1.0,
        )
