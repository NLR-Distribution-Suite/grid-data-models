"""This module contains interface for distribution transformer."""

from itertools import groupby
from typing import Annotated

from infrasys import Component
from pydantic import Field, model_validator

from gdm.systems.distribution.enums import ConnectionType, VoltageTypes, TransformerMounting
from gdm.systems.distribution.common.sequence_pair import SequencePair
from gdm.quantities import ApparentPower, Voltage
from gdm.constants import PINT_SCHEMA


class WindingEquipment(Component):
    """Data model for winding."""

    name: Annotated[str, Field("", description="Name of the winding.")]
    resistance: Annotated[
        float,
        Field(
            ...,
            strict=True,
            ge=0,
            le=100,
            description="Percentage resistance for this winding.",
        ),
    ]
    is_grounded: Annotated[bool, Field(..., description="Is this winding grounded or not.")]
    rated_voltage: Annotated[
        Voltage,
        PINT_SCHEMA,
        Field(..., description="rated voltage rating for this winding.", gt=0),
    ]
    voltage_type: Annotated[
        VoltageTypes,
        Field(..., description="Set voltage type for rated voltage."),
    ]
    rated_power: Annotated[
        ApparentPower,
        PINT_SCHEMA,
        Field(..., description="Rated power for this winding.", gt=0),
    ]
    num_phases: Annotated[
        int,
        Field(..., ge=1, le=3, description="Number of phases for this winding."),
    ]
    connection_type: Annotated[
        ConnectionType,
        Field(
            ...,
            description="""Connection type for this winding.""",
        ),
    ]
    tap_positions: Annotated[
        list[float],
        Field(
            ...,
            description="List of per unit tap positions for each phase. Centered at 1.0.",
        ),
    ]
    total_taps: Annotated[
        int,
        Field(default=32, description="Total number of taps along the bandwidth."),
    ]
    min_tap_pu: Annotated[
        float,
        Field(0.9, le=1.0, ge=0, description="Min tap in pu for this winding."),
    ]
    max_tap_pu: Annotated[
        float,
        Field(1.1, ge=1.0, description="Min tap in pu for this winding."),
    ]

    @model_validator(mode="after")
    def validate_fields(self) -> "WindingEquipment":
        """Custom validator for winding fields."""
        if not len(self.tap_positions) == self.num_phases:
            msg = (
                f"Number of tap positions {self.tap_positions=}"
                f"should be equal to number of phase {self.num_phases}"
            )
            raise ValueError(msg)
        for tap in self.tap_positions:
            if not (self.min_tap_pu <= tap <= self.max_tap_pu):
                msg = (
                    f"Tap position {tap=} outside allowable range"
                    f" of [{self.min_tap_pu=}-{self.max_tap_pu=}] for"
                    f" this winding."
                )
                raise ValueError(msg)

        return self

    @classmethod
    def example(cls) -> "WindingEquipment":
        return WindingEquipment(
            resistance=1,
            is_grounded=False,
            rated_voltage=Voltage(12.47, "kilovolt"),
            rated_power=ApparentPower(500, "kilova"),
            connection_type=ConnectionType.STAR,
            num_phases=3,
            tap_positions=[1.0, 1.0, 1.0],
            total_taps=32,
            voltage_type=VoltageTypes.LINE_TO_LINE,
        )


class DistributionTransformerEquipment(Component):
    """Data model for distribution transformer info."""

    mounting: Annotated[
        TransformerMounting,
        Field(TransformerMounting.POLE_MOUNT, description="Transformer mounting type."),
    ]
    pct_no_load_loss: Annotated[
        float,
        Field(
            ...,
            strict=True,
            ge=0,
            le=100,
            description="Percentage no load losses for this transformer.",
        ),
    ]
    pct_full_load_loss: Annotated[
        float,
        Field(
            ...,
            strict=True,
            ge=0,
            le=100,
            description="Percentage no load losses for this transformer.",
        ),
    ]
    windings: Annotated[
        list[WindingEquipment],
        Field(..., description="List of windings for this transformer."),
    ]

    coupling_sequences: Annotated[
        list[SequencePair],
        Field(
            ...,
            description="""List of pair
            of sequence numbers for coupling """,
        ),
    ]
    winding_reactances: Annotated[
        list[Annotated[float, Field(strict=True, ge=0, le=100)]],
        Field(
            ...,
            description="""Winding coupling reactances in the
            "same order as coupling sequences.""",
        ),
    ]
    is_center_tapped: Annotated[bool, Field(..., description="Is this transformer center tapped.")]

    @model_validator(mode="after")
    def validate_fields(self) -> "DistributionTransformerEquipment":
        """Custom validator for distribution transformer model."""

        for wdg_seq in self.coupling_sequences:
            if wdg_seq.from_index == wdg_seq.to_index:
                msg = (
                    f"From sequence number {wdg_seq.from_index} can not "
                    f"be same as To sequence {wdg_seq.to_index} numbers."
                )
                raise ValueError(msg)

        if len(self.coupling_sequences) != sum(range(len(self.windings))):
            msg = (
                f"Length of winding couplings is invalid."
                f"Phase couplings: {len(self.coupling_sequences)},"
                f"Windings {len(self.windings)}"
            )
            raise ValueError(msg)

        if len(self.coupling_sequences) != len(self.winding_reactances):
            msg = (
                f"Length of coupling sequences {self.coupling_sequences=}"
                f"must be equal to length of winding reactances {self.winding_reactances}"
            )
            raise ValueError(msg)

        if len(list(groupby([set(item) for item in self.coupling_sequences]))) != len(
            self.coupling_sequences
        ):
            msg = f"Invalid sequence numbers in spacing sequences. {self.coupling_sequences=}"
            raise ValueError(msg)

        return self

    @classmethod
    def example(cls) -> "DistributionTransformerEquipment":
        """Example for distribution transformer model."""
        return DistributionTransformerEquipment(
            name="Transformer-1",
            pct_no_load_loss=0.1,
            pct_full_load_loss=1,
            is_center_tapped=False,
            mounting=TransformerMounting.PAD_MOUNT,
            windings=[
                WindingEquipment(
                    resistance=1,
                    is_grounded=False,
                    rated_voltage=Voltage(12.47, "kilovolt"),
                    rated_power=ApparentPower(56, "kilova"),
                    connection_type=ConnectionType.STAR,
                    num_phases=3,
                    tap_positions=[1.0, 1.0, 1.0],
                    voltage_type=VoltageTypes.LINE_TO_LINE,
                ),
                WindingEquipment(
                    resistance=1,
                    is_grounded=False,
                    rated_voltage=Voltage(0.4, "kilovolt"),
                    rated_power=ApparentPower(56, "kilova"),
                    connection_type=ConnectionType.STAR,
                    num_phases=3,
                    tap_positions=[1.0, 1.0, 1.0],
                    voltage_type=VoltageTypes.LINE_TO_LINE,
                ),
            ],
            coupling_sequences=[SequencePair(0, 1)],
            winding_reactances=[2.3],
        )
