"""This module contains concentric cable equipment."""

from typing import Annotated

from infrasys import Component
from pydantic import Field, PositiveInt, model_validator

from gdm.systems.distribution.enums import WireInsulationType
from gdm.quantities import (
    ResistancePULength,
    Distance,
    Current,
    Voltage,
)
from gdm.constants import PINT_SCHEMA


class ConcentricCableEquipment(Component):
    """Data model for cable catalog."""

    strand_diameter: Annotated[
        Distance, PINT_SCHEMA, Field(..., description="Diameter of the cable strand.", gt=0)
    ]
    conductor_diameter: Annotated[
        Distance,
        PINT_SCHEMA,
        Field(..., description="Diameter of the conductor inside cable.", gt=0),
    ]
    cable_diameter: Annotated[
        Distance, PINT_SCHEMA, Field(..., description="Diameter of the cable.", gt=0)
    ]
    insulation_thickness: Annotated[
        Distance, PINT_SCHEMA, Field(..., description="Thickness of insulation.", gt=0)
    ]
    insulation_diameter: Annotated[
        Distance, PINT_SCHEMA, Field(..., description="Diameter of the insulation.", gt=0)
    ]
    ampacity: Annotated[
        Current, PINT_SCHEMA, Field(..., description="Ampacity of the conductor.", gt=0)
    ]
    conductor_gmr: Annotated[
        Distance,
        PINT_SCHEMA,
        Field(..., description="Geometric mean radius of the conductor.", gt=0),
    ]
    strand_gmr: Annotated[
        Distance,
        PINT_SCHEMA,
        Field(..., description="Geometric mean radius of the strand.", gt=0),
    ]
    phase_ac_resistance: Annotated[
        ResistancePULength,
        PINT_SCHEMA,
        Field(..., description="Per unit length conductor ac resistance.", gt=0),
    ]
    strand_ac_resistance: Annotated[
        ResistancePULength,
        PINT_SCHEMA,
        Field(..., description="Per unit length ac resistance of the strand.", gt=0),
    ]
    num_neutral_strands: Annotated[
        PositiveInt, Field(..., description="Number of neutral strands in the cable.")
    ]
    rated_voltage: Annotated[
        Voltage, PINT_SCHEMA, Field(..., description="Rated voltage for the cable.", gt=0)
    ]
    insulation: Annotated[
        WireInsulationType,
        PINT_SCHEMA,
        Field(WireInsulationType.PE, description="Wire insulation type"),
    ]

    @model_validator(mode="after")
    def validate_fields(self) -> "ConcentricCableEquipment":
        """Custom validator for fields."""
        if self.insulation_diameter.to("m") < (
            self.conductor_diameter.to("m") + 2 * self.insulation_thickness.to("m")
        ):
            msg = (
                f"Insulation diameter {self.insulation_diameter} must be greater than "
                f"conductor diameter {self.conductor_diameter} plus two times insulation "
                f"thickness {self.insulation_thickness}"
            )
            raise ValueError(msg)

        if self.cable_diameter < (self.insulation_diameter + 2 * self.strand_diameter):
            msg = (
                f"Cable diameter {self.cable_diameter} must be greater than "
                f"insulation diameter {self.insulation_diameter} plus two times strand diameter "
                f" {self.strand_diameter}"
            )
            raise ValueError(msg)
        return self

    @classmethod
    def example(cls) -> "ConcentricCableEquipment":
        """Example for concentric cable."""
        return ConcentricCableEquipment(
            name="2(7×)concentric_cable_1/3",
            strand_diameter=Distance(0.0641, "in"),
            conductor_diameter=Distance(0.258, "in"),
            cable_diameter=Distance(0.98, "in"),
            insulation_thickness=Distance(0.226, "in"),
            insulation_diameter=Distance(0.78, "in"),
            ampacity=Current(135, "ampere"),
            conductor_gmr=Distance(0.00836, "ft"),
            strand_gmr=Distance(0.00208, "ft"),
            phase_ac_resistance=ResistancePULength(0.945, "ohm/mi"),
            strand_ac_resistance=ResistancePULength(14.8722, "ohm/mi"),
            num_neutral_strands=2,
            rated_voltage=Voltage(15, "kilovolt"),
            insulation=WireInsulationType.XLPE,
        )
