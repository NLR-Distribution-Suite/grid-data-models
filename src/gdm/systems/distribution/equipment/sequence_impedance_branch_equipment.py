"""This module contains sequence impedance branch equipment."""

from typing import Annotated

from infrasys import Component
from pydantic import Field

from gdm.quantities import (
    Current,
    ResistancePULength,
    ReactancePULength,
    CapacitancePULength,
)
from gdm.constants import PINT_SCHEMA


class SequenceImpedanceBranchEquipment(Component):
    """Data model for sequence impedance branch."""

    pos_seq_resistance: Annotated[
        ResistancePULength,
        PINT_SCHEMA,
        Field(..., description="Per unit length positive sequence resistance."),
    ]
    zero_seq_resistance: Annotated[
        ResistancePULength,
        PINT_SCHEMA,
        Field(..., description="Per unit length zero sequence impedance."),
    ]
    pos_seq_reactance: Annotated[
        ReactancePULength,
        PINT_SCHEMA,
        Field(..., description="Per unit length positive sequence impedance."),
    ]
    zero_seq_reactance: Annotated[
        ReactancePULength,
        PINT_SCHEMA,
        Field(..., description="Per unit length zero sequence impedance."),
    ]
    pos_seq_capacitance: Annotated[
        CapacitancePULength,
        PINT_SCHEMA,
        Field(..., description="Per unit length positive sequence capacitance."),
    ]
    zero_seq_capacitance: Annotated[
        CapacitancePULength,
        PINT_SCHEMA,
        Field(..., description="Per unit length zero sequence capacitance."),
    ]
    ampacity: Annotated[
        Current, PINT_SCHEMA, Field(..., description="Ampacity of the conductor.", gt=0)
    ]

    @classmethod
    def example(cls) -> "SequenceImpedanceBranchEquipment":
        """Example for sequence impedance branch model."""
        return SequenceImpedanceBranchEquipment(
            name="sequence-impedance-branch-1",
            pos_seq_resistance=ResistancePULength(0.304, "ohm/mi"),
            zero_seq_resistance=ResistancePULength(0.45, "ohm/mi"),
            pos_seq_reactance=ReactancePULength(0.4, "ohm/mi"),
            zero_seq_reactance=ReactancePULength(0.4, "ohm/mi"),
            pos_seq_capacitance=CapacitancePULength(900, "nanofarad/mi"),
            zero_seq_capacitance=CapacitancePULength(700, "nanofarad/mi"),
            ampacity=Current(90, "ampere"),
        )
