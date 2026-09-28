"""This module contains distribution recloser controller."""

from typing import Annotated

from pydantic import Field, model_validator
from infrasys.quantities import Time
from infrasys import Component

from gdm.systems.distribution.equipment.recloser_controller_equipment import (
    RecloserControllerEquipment,
)
from gdm.systems.distribution.common.curve import TimeCurrentCurve
from gdm.constants import PINT_SCHEMA


class DistributionRecloserController(Component):
    """Data model for distribution recloser controller."""

    name: Annotated[str, Field("", description="Name of the recloser controller.")]

    delay: Annotated[
        Time, PINT_SCHEMA, Field(description="Fixed delay added to the recloser trip time.")
    ]
    ground_delayed: Annotated[
        TimeCurrentCurve, Field(description="TCC curve related to ground delayed trip.")
    ]
    ground_fast: Annotated[
        TimeCurrentCurve, Field(description="TCC curve related to ground fast trip.")
    ]
    phase_delayed: Annotated[
        TimeCurrentCurve, Field(description="TCC curve related to phase delayed trip.")
    ]
    phase_fast: Annotated[
        TimeCurrentCurve, Field(description="TCC curve related to phase fast trip.")
    ]
    num_fast_ops: Annotated[
        int, Field(ge=0, description="Number of fast operations (fuse savings).")
    ]
    num_shots: Annotated[
        int, Field(ge=1, description="Number of fast and delayed shots before lockout.")
    ]
    reclose_intervals: Annotated[
        Time, PINT_SCHEMA, Field(..., description="Array of reclose intervals.")
    ]
    reset_time: Annotated[Time, PINT_SCHEMA, Field(..., description="Reset time for recloser.")]
    equipment: Annotated[
        RecloserControllerEquipment, Field(..., description="Recloser controller equipment.")
    ]

    @model_validator(mode="after")
    def validate_fields(self) -> "DistributionRecloserController":
        """Validate fields for DistributionRecloserController."""

        if len(self.reclose_intervals) != (self.num_shots - 1):
            msg = (
                f"Length of {self.reclose_intervals=} must be one less than"
                f" the length of {self.num_shots=}"
            )
            raise ValueError(msg)
        return self

    @classmethod
    def example(cls) -> "DistributionRecloserController":
        """Example for distribution recloser controller."""
        return DistributionRecloserController(
            delay=Time(0, "minutes"),
            ground_delayed=TimeCurrentCurve.example(),
            ground_fast=TimeCurrentCurve.example(),
            phase_delayed=TimeCurrentCurve.example(),
            phase_fast=TimeCurrentCurve.example(),
            num_fast_ops=1,
            num_shots=4,
            reclose_intervals=Time([0.2, 20, 20], "second"),
            reset_time=Time(20, "second"),
            equipment=RecloserControllerEquipment.example(),
        )
