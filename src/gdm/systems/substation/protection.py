"""Substation protection, settings, and test records."""

from __future__ import annotations

from datetime import datetime

from infrasys import Component
from pydantic import Field

from gdm.systems.substation.components import PrimaryEquipmentComponent
from gdm.systems.substation.enums import ProtectionFunctionType
from gdm.systems.substation.metering import InstrumentTransformerCore
from gdm.systems.substation.models import DocumentReference, StateObservation
from gdm.systems.substation.topology import Bay


class ProtectionIED(Component):
    """Protection or control IED identity and configuration baseline."""

    manufacturer: str | None = None
    model: str | None = None
    firmware_version: str | None = None
    hardware_revision: str | None = None
    ied_name: str | None = None
    bay: Bay | None = None
    documents: list[DocumentReference] = Field(default_factory=list)
    active_setting_group_id: str | None = None

    @classmethod
    def example(cls) -> "ProtectionIED":
        return cls(
            name="feeder-relay-001",
            manufacturer="example",
            model="feeder-relay",
            firmware_version="1.0",
            ied_name="IED_FEEDER_001",
        )


class ProtectionSetting(Component):
    """One approved or observed protection setting."""

    parameter: str
    value: float | str | bool
    unit: str | None = None
    phase_scope: str | None = None

    @classmethod
    def example(cls) -> "ProtectionSetting":
        return cls(
            name="phase-pickup",
            parameter="pickup_current",
            value=480,
            unit="ampere",
            phase_scope="ABC",
        )


class ProtectionSettingGroup(Component):
    """Named relay setting group with lifecycle state."""

    group_name: str
    settings: list[ProtectionSetting] = Field(default_factory=list)
    approved: bool = False
    loaded_at: datetime | None = None

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
    ied: ProtectionIED
    protects_equipment: list[PrimaryEquipmentComponent] = Field(default_factory=list)
    input_cores: list[InstrumentTransformerCore] = Field(default_factory=list)
    output_equipment: list[PrimaryEquipmentComponent] = Field(default_factory=list)
    setting_groups: list[ProtectionSettingGroup] = Field(default_factory=list)
    state_observations: list[StateObservation] = Field(default_factory=list)

    @classmethod
    def example(cls) -> "ProtectionFunction":
        return cls(
            name="feeder-overcurrent-001",
            function_type=ProtectionFunctionType.OVERCURRENT,
            ansi_function_number="50/51",
            ied=ProtectionIED.example(),
            input_cores=[InstrumentTransformerCore.example()],
            setting_groups=[ProtectionSettingGroup.example()],
        )


class ProtectionScheme(Component):
    """Coordinated protection functions for a zone or bay."""

    zone: str
    functions: list[ProtectionFunction] = Field(default_factory=list)
    equipment: list[PrimaryEquipmentComponent] = Field(default_factory=list)
    documents: list[DocumentReference] = Field(default_factory=list)

    @classmethod
    def example(cls) -> "ProtectionScheme":
        return cls(
            name="feeder-protection-scheme-001",
            zone="feeder-001",
            functions=[ProtectionFunction.example()],
        )


class ProtectionTest(Component):
    """Evidence record for a protection or control test."""

    test_type: str
    tested_object: Component
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
            tested_object=ProtectionIED.example(),
            result="pass",
            performed_at=datetime(2025, 1, 1),
        )
