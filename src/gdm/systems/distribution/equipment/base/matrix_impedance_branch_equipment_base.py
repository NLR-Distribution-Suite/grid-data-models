"""This module contains matrix impedance branch equipment."""

from typing import Annotated

from infrasys import Component
from pydantic import Field, model_validator

from gdm.systems.distribution.enums import LineType
from gdm.quantities import (
    ResistancePULength,
    ReactancePULength,
    CapacitancePULength,
    Current,
)

from gdm.constants import PINT_SCHEMA


class MatrixImpedanceBranchEquipmentBase(Component):
    """Data model for impedance based branch."""

    construction: Annotated[
        LineType,
        PINT_SCHEMA,
        Field(
            LineType.OVERHEAD,
            description="Construction type of MatrixImpedanceBranchEquipmentBase.",
        ),
    ]
    r_matrix: Annotated[
        ResistancePULength,
        PINT_SCHEMA,
        Field(..., description="Per unit length resistance matrix."),
    ]
    x_matrix: Annotated[
        ReactancePULength,
        PINT_SCHEMA,
        Field(..., description="Per unit length reactance matrix."),
    ]
    c_matrix: Annotated[
        CapacitancePULength,
        PINT_SCHEMA,
        Field(..., description="Per unit length capacitance matrix."),
    ]
    ampacity: Annotated[
        Current, PINT_SCHEMA, Field(..., description="Ampacity of the conductor.", gt=0)
    ]

    @model_validator(mode="after")
    def validate_fields(self) -> "MatrixImpedanceBranchEquipmentBase":
        """Custom validator for fields."""
        if self.r_matrix.shape == self.x_matrix.shape == self.c_matrix.shape:
            return self

        msg = f"matrix sizes are not equals {self.r_matrix=} {self.x_matrix=} {self.c_matrix=}"
        raise ValueError(msg)
