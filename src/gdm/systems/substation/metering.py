"""Substation metering and power-quality models."""

from datetime import datetime

from pydantic import Field
from infrasys import Component

from gdm.systems.substation.enums import MeasurementPurpose


class InstrumentTransformerCore(Component):
    """Individual CT/VT core assigned to protection or metering."""

    core_type: str
    purpose: MeasurementPurpose
    accuracy_class: str | None = None
    burden_va: float | None = Field(None, ge=0)
    instrument_transformer_id: str

    @classmethod
    def example(cls) -> "InstrumentTransformerCore":
        return cls(
            name="feeder-ct-metering-core",
            core_type="metering",
            purpose=MeasurementPurpose.REVENUE,
            accuracy_class="0.3B0.1",
            instrument_transformer_id="feeder-ct-001",
        )


class MeteringPoint(Component):
    """Metering point at a station or interconnection boundary."""

    purpose: MeasurementPurpose
    terminal_id: str
    meter_id: str
    instrument_core_ids: list[str] = Field(default_factory=list)
    multiplier: float = Field(1, gt=0)
    interval_seconds: int | None = Field(None, gt=0)
    owner: str | None = None

    @classmethod
    def example(cls) -> "MeteringPoint":
        return cls(
            name="feeder-metering-point",
            purpose=MeasurementPurpose.OPERATIONAL,
            terminal_id="feeder-breaker-feeder-terminal",
            meter_id="feeder-meter-001",
            instrument_core_ids=["feeder-ct-metering-core"],
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

    terminal_id: str
    measurement_method: str
    monitored_phenomena: list[str] = Field(default_factory=list)
    sample_rate_hz: float | None = Field(None, gt=0)
    observation_window_seconds: int | None = Field(None, gt=0)
    pcc: bool = False

    @classmethod
    def example(cls) -> "PowerQualityMonitor":
        return cls(
            name="feeder-pq-monitor",
            terminal_id="feeder-breaker-feeder-terminal",
            measurement_method="IEEE 1159",
            monitored_phenomena=["voltage_sag", "harmonics", "flicker"],
        )
