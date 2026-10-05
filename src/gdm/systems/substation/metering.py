"""Substation metering and power-quality models."""

from __future__ import annotations

from datetime import datetime

from infrasys import Component
from pydantic import Field

from gdm.systems.substation.enums import MeasurementPurpose
from gdm.systems.substation.topology import BusbarSection


class InstrumentTransformerCore(Component):
    """Individual CT/VT core assigned to protection or metering."""

    core_type: str
    purpose: MeasurementPurpose
    accuracy_class: str | None = None
    burden_va: float | None = Field(None, ge=0)

    @classmethod
    def example(cls) -> "InstrumentTransformerCore":
        return cls(
            name="feeder-ct-metering-core",
            core_type="metering",
            purpose=MeasurementPurpose.REVENUE,
            accuracy_class="0.3B0.1",
        )


class MeteringPoint(Component):
    """Metering point at a station or interconnection boundary."""

    purpose: MeasurementPurpose
    bus: BusbarSection
    meter_id: str
    cores: list[InstrumentTransformerCore] = Field(default_factory=list)
    multiplier: float = Field(1, gt=0)
    interval_seconds: int | None = Field(None, gt=0)
    owner: str | None = None

    @classmethod
    def example(cls) -> "MeteringPoint":
        return cls(
            name="feeder-metering-point",
            purpose=MeasurementPurpose.OPERATIONAL,
            bus=BusbarSection.example(),
            meter_id="feeder-meter-001",
            cores=[InstrumentTransformerCore.example()],
        )


class MeterTest(Component):
    """Meter calibration or verification record."""

    meter_id: str
    tested_at: datetime
    result: str
    accuracy_class: str | None = None
    report_reference_id: str | None = None

    @classmethod
    def example(cls) -> "MeterTest":
        return cls(
            name="feeder-meter-test",
            meter_id="feeder-meter-001",
            tested_at=datetime(2025, 1, 1),
            result="pass",
        )


class PowerQualityMonitor(Component):
    """Power-quality monitoring point and method metadata."""

    bus: BusbarSection
    measurement_method: str
    monitored_phenomena: list[str] = Field(default_factory=list)
    sample_rate_hz: float | None = Field(None, gt=0)
    observation_window_seconds: int | None = Field(None, gt=0)
    pcc: bool = False

    @classmethod
    def example(cls) -> "PowerQualityMonitor":
        return cls(
            name="feeder-pq-monitor",
            bus=BusbarSection.example(),
            measurement_method="IEEE 1159",
            monitored_phenomena=["voltage_sag", "harmonics", "flicker"],
        )
