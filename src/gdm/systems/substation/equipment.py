"""Substation primary equipment models."""

from typing import Annotated

from pydantic import Field

from gdm.constants import PINT_SCHEMA
from gdm.quantities import Frequency, Voltage
from gdm.systems.substation.components import PrimaryEquipmentComponent


class InstrumentTransformer(PrimaryEquipmentComponent):
    """Current or voltage transformer with measurement/protection cores."""

    instrument_type: str
    primary_rating: float = Field(..., gt=0)
    secondary_rating: float = Field(..., gt=0)
    ratio_unit: str
    core_ids: list[str] = Field(default_factory=list)
    accuracy_class: str | None = None
    knee_point_voltage: float | None = Field(None, gt=0)

    @classmethod
    def example(cls) -> "InstrumentTransformer":
        return cls(
            name="feeder-ct-001",
            bay_id="feeder-bay-001",
            instrument_type="current_transformer",
            primary_rating=600,
            secondary_rating=5,
            ratio_unit="ampere",
            core_ids=["feeder-ct-protection-core", "feeder-ct-metering-core"],
        )


class SurgeArrester(PrimaryEquipmentComponent):
    """Station surge arrester."""

    mcov: Voltage
    arrester_class: str | None = None
    terminal_id: str
    ground_terminal_id: str | None = None

    @classmethod
    def example(cls) -> "SurgeArrester":
        return cls(
            name="mv-surge-arrester-001",
            bay_id="feeder-bay-001",
            mcov=Voltage(15.3, "kilovolt"),
            arrester_class="distribution",
            terminal_id="mv-bus-node",
        )


class LineTrap(PrimaryEquipmentComponent):
    """Carrier-wave line trap connected in series with an external circuit."""

    terminal_ids: list[str] = Field(min_length=2, max_length=2)
    tuning_frequency_hz: Annotated[Frequency | None, PINT_SCHEMA, Field(None, gt=0)]

    @classmethod
    def example(cls) -> "LineTrap":
        return cls(
            name="incoming-line-trap-001",
            bay_id="incoming-line-bay-001",
            terminal_ids=["line-trap-station-terminal", "line-trap-line-terminal"],
            tuning_frequency_hz=Frequency(100_000, "hertz"),
        )
