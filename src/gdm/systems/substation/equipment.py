"""Substation primary equipment models."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, model_validator

from gdm.constants import PINT_SCHEMA
from gdm.quantities import Frequency, Voltage
from gdm.systems.substation.components import PrimaryEquipmentComponent
from gdm.systems.substation.metering import InstrumentTransformerCore
from gdm.systems.substation.topology import BusbarSection


class InstrumentTransformer(PrimaryEquipmentComponent):
    """Current or voltage transformer with measurement/protection cores.

    ``buses`` contains one node for a shunt-connected device (PT/CVT) or two
    nodes for a series-connected device (CT).
    """

    instrument_type: str
    primary_rating: float = Field(..., gt=0)
    secondary_rating: float = Field(..., gt=0)
    ratio_unit: str
    cores: list[InstrumentTransformerCore] = Field(default_factory=list)
    accuracy_class: str | None = None
    knee_point_voltage: float | None = Field(None, gt=0)
    buses: list[BusbarSection]

    @model_validator(mode="after")
    def validate_buses(self) -> "InstrumentTransformer":
        if len(self.buses) not in (1, 2):
            raise ValueError("InstrumentTransformer requires one (shunt) or two (series) buses.")
        if len(self.buses) == 2 and self.buses[0].name == self.buses[1].name:
            raise ValueError("InstrumentTransformer series buses must be distinct.")
        return self

    @classmethod
    def example(cls) -> "InstrumentTransformer":
        return cls(
            name="feeder-ct-001",
            instrument_type="current_transformer",
            primary_rating=600,
            secondary_rating=5,
            ratio_unit="ampere",
            cores=[InstrumentTransformerCore.example()],
            buses=[BusbarSection.example()],
        )


class SurgeArrester(PrimaryEquipmentComponent):
    """Station surge arrester."""

    mcov: Voltage
    arrester_class: str | None = None
    bus: BusbarSection
    ground_bus: BusbarSection | None = None

    @classmethod
    def example(cls) -> "SurgeArrester":
        return cls(
            name="mv-surge-arrester-001",
            mcov=Voltage(15.3, "kilovolt"),
            arrester_class="distribution",
            bus=BusbarSection.example(),
        )


class LineTrap(PrimaryEquipmentComponent):
    """Carrier-wave line trap connected in series with an external circuit."""

    buses: list[BusbarSection] = Field(min_length=2, max_length=2)
    tuning_frequency_hz: Annotated[Frequency | None, PINT_SCHEMA, Field(None, gt=0)]

    @classmethod
    def example(cls) -> "LineTrap":
        voltage_level = BusbarSection.example().voltage_level
        return cls(
            name="incoming-line-trap-001",
            buses=[
                BusbarSection.example(),
                BusbarSection(
                    name="line-trap-line-node",
                    voltage_level=voltage_level,
                    rated_voltage=Voltage(12.47, "kilovolt"),
                ),
            ],
            tuning_frequency_hz=Frequency(100_000, "hertz"),
        )
