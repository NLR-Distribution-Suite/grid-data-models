"""This module contains interface for distribution controllers."""

from typing import Annotated, Optional

from infrasys.quantities import Time
from infrasys import Component
from pydantic import Field

from gdm.systems.distribution.components.distribution_bus import DistributionBus
from gdm.systems.distribution.enums import Phase
from gdm.quantities import (
    Voltage,
    Current,
)

from gdm.constants import PINT_SCHEMA


class RegulatorController(Component):
    """Data model for a Regulator Controller."""

    name: Annotated[str, Field("", description="Name of the regulator controller.")]

    tapped_winding: Annotated[
        Optional[int],
        Field(
            2,
            ge=1,
            le=3,
            description="The index of the winding on the transformer that this controller is controlling.",
        ),
    ]

    delay: Annotated[
        Optional[Time],
        PINT_SCHEMA,
        Field(..., description="Delay for the first tap change operation"),
    ]
    v_setpoint: Annotated[
        Voltage,
        PINT_SCHEMA,
        Field(..., description="The target control voltage for regulator controller.", gt=0),
    ]
    min_v_limit: Annotated[
        Voltage,
        PINT_SCHEMA,
        Field(..., description="The minimum voltage limit for regulator controller.", gt=0),
    ]
    max_v_limit: Annotated[
        Voltage,
        PINT_SCHEMA,
        Field(..., description="The maximum voltage limit for regulator controller.", gt=0),
    ]
    pt_ratio: Annotated[
        float,
        Field(
            ...,
            ge=0,
            description="Value of the voltage (potential) transformer ratio used to step down the voltage for the controller.",
        ),
    ]
    use_ldc: Annotated[
        bool,
        Field(
            ...,
            description="Boolean value representing whether the line drop compensator is used or not.",
        ),
    ]
    is_reversible: Annotated[
        bool,
        Field(
            ...,
            description="Boolean value representing whether the tap change is reversible or not.",
        ),
    ]
    ldc_R: Annotated[
        Optional[Voltage],
        PINT_SCHEMA,
        Field(
            None,
            description="R setting on the line drop compensator of the regulator in Volts.",
            ge=0,
        ),
    ]
    ldc_X: Annotated[
        Optional[Voltage],
        PINT_SCHEMA,
        Field(
            None,
            description="X setting on the line drop compensator of the regulator in Volts.",
            ge=0,
        ),
    ]
    ct_primary: Annotated[
        Optional[Current],
        PINT_SCHEMA,
        Field(
            None,
            description="Current at which the line drop compensator voltages match the R and X settings.",
            ge=0,
        ),
    ]
    max_step: Annotated[
        int,
        Field(
            ge=0,
            description="Maximum number of steps upwards or downwards that can be made per control iteration.",
        ),
    ]
    bandwidth: Annotated[
        Voltage,
        PINT_SCHEMA,
        Field(..., description="The total voltage bandwidth for the controller", ge=0),
    ]
    controlled_bus: Annotated[
        DistributionBus,
        Field(..., description="The bus that is being controlled by the controller."),
    ]

    controlled_phase: Annotated[
        Phase,
        Field(..., description="The phase that is being controlled by the controller."),
    ]

    @classmethod
    def example(cls) -> "RegulatorController":
        """Example for a Regulator Controller."""
        return RegulatorController(
            delay=Time(10, "seconds"),
            v_setpoint=Voltage(120, "volts"),
            min_v_limit=Voltage(132, "volts"),
            max_v_limit=Voltage(102, "volts"),
            is_reversible=False,
            use_ldc=True,
            ct_primary=Current(0.1, "ampere"),
            pt_ratio=60,
            max_step=16,
            bandwidth=Voltage(3, "volts"),
            controlled_bus=DistributionBus.example(),
            controlled_phase=Phase.A,
        )
