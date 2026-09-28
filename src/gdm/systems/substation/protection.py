"""Substation protection, settings, and test records."""

from datetime import datetime

from pydantic import Field
from infrasys import Component

from gdm.systems.substation.enums import ProtectionFunctionType
from gdm.systems.substation.models import DocumentReference, StateObservation


class ProtectionIED(Component):
    """Protection or control IED identity and configuration baseline."""

    manufacturer: str | None = None
    model: str | None = None
    firmware_version: str | None = None
    hardware_revision: str | None = None
    ied_name: str | None = None
    bay_id: str | None = None
    document_reference_ids: list[str] = Field(default_factory=list)
    active_setting_group_id: str | None = None

    @classmethod
    def example(cls) -> "ProtectionIED":
        return cls(
            name="feeder-relay-001",
            manufacturer="example",
            model="feeder-relay",
            firmware_version="1.0",
            ied_name="IED_FEEDER_001",
            bay_id="feeder-bay-001",
        )


class ProtectionSetting(Component):
    """One approved or observed protection setting."""

    parameter: str
    value: float | str | bool
    unit: str | None = None
    setting_group_id: str
    phase_scope: str | None = None

    @classmethod
    def example(cls) -> "ProtectionSetting":
        return cls(
            name="phase-pickup",
            parameter="pickup_current",
            value=480,
            unit="ampere",
            setting_group_id="feeder-relay-group-1",
            phase_scope="ABC",
        )


class ProtectionSettingGroup(Component):
    """Named relay setting group with lifecycle state."""

    group_name: str
    settings: list[ProtectionSetting] = Field(default_factory=list)
    approved: bool = False
    loaded_at: datetime | None = None
    supersedes_group_id: str | None = None

    @classmethod
    def example(cls) -> "ProtectionSettingGroup":
        return cls(
            name="feeder-relay-group-1",
            group_name="normal",
            settings=[ProtectionSetting.example()],
            approved=True,
        )


class ProtectionFunction(Component):
    """Protection function linked to equipment, inputs, and trip outputs."""

    function_type: ProtectionFunctionType
    ansi_function_number: str | None = None
    instance: str | None = None
    ied_id: str
    protects_equipment_ids: list[str] = Field(default_factory=list)
    input_core_ids: list[str] = Field(default_factory=list)
    output_equipment_ids: list[str] = Field(default_factory=list)
    setting_group_ids: list[str] = Field(default_factory=list)
    state_observations: list[StateObservation] = Field(default_factory=list)

    @classmethod
    def example(cls) -> "ProtectionFunction":
        return cls(
            name="feeder-overcurrent-001",
            function_type=ProtectionFunctionType.OVERCURRENT,
            ansi_function_number="50/51",
            ied_id="feeder-relay-001",
            protects_equipment_ids=["feeder-breaker-001"],
            input_core_ids=["feeder-ct-protection-core"],
            output_equipment_ids=["feeder-breaker-001"],
            setting_group_ids=["feeder-relay-group-1"],
        )


class ProtectionScheme(Component):
    """Coordinated protection functions for a zone or bay."""

    zone: str
    function_ids: list[str] = Field(default_factory=list)
    equipment_ids: list[str] = Field(default_factory=list)
    document_reference_ids: list[str] = Field(default_factory=list)

    @classmethod
    def example(cls) -> "ProtectionScheme":
        return cls(
            name="feeder-protection-scheme-001",
            zone="feeder-001",
            function_ids=["feeder-overcurrent-001"],
            equipment_ids=["feeder-breaker-001"],
        )


class ProtectionTest(Component):
    """Evidence record for a protection or control test."""

    test_type: str
    tested_object_id: str
    procedure: str | None = None
    result: str
    performed_at: datetime
    performed_by: str | None = None
    document_reference: DocumentReference | None = None

    @classmethod
    def example(cls) -> "ProtectionTest":
        return cls(
            name="feeder-relay-commissioning-test",
            test_type="commissioning",
            tested_object_id="feeder-relay-001",
            result="pass",
            performed_at=datetime(2025, 1, 1),
        )
