"""Station automation and SCADA protocol mappings."""

from __future__ import annotations

from infrasys import Component
from pydantic import Field

from gdm.systems.substation.components import PrimaryEquipmentComponent
from gdm.systems.substation.enums import ProtocolType
from gdm.systems.substation.topology import Bay


class ProtocolEndpoint(Component):
    """Protocol endpoint such as a DNP3 outstation or IEC 60870 link."""

    protocol: ProtocolType
    address: str
    host: str | None = None
    port: int | None = Field(None, ge=0, le=65535)
    secure: bool = False

    @classmethod
    def example(cls) -> "ProtocolEndpoint":
        return cls(
            name="station-dnp3-endpoint",
            protocol=ProtocolType.DNP3,
            address="outstation-1",
            host="station-rtu",
            port=20000,
        )


class IED(Component):
    """Station automation IED, RTU, gateway, or controller."""

    device_type: str
    manufacturer: str | None = None
    model: str | None = None
    firmware_version: str | None = None
    bay: Bay | None = None
    logical_device_ids: list[str] = Field(default_factory=list)
    protocol_endpoints: list[ProtocolEndpoint] = Field(default_factory=list)

    @classmethod
    def example(cls) -> "IED":
        return cls(
            name="station-ied-001",
            device_type="bay_controller",
            manufacturer="example",
            model="station-controller",
            protocol_endpoints=[ProtocolEndpoint.example()],
        )


class LogicalNode(Component):
    """IEC 61850 logical-node instance hosted by an IED."""

    ied: IED
    logical_device: str
    logical_node_class: str
    instance: str
    primary_equipment: PrimaryEquipmentComponent | None = None
    function_id: str | None = None

    @classmethod
    def example(cls) -> "LogicalNode":
        return cls(
            name="x-circuit-breaker-001",
            ied=IED.example(),
            logical_device="LD_FEEDER_001",
            logical_node_class="XCBR",
            instance="1",
        )


class SCLConfiguration(Component):
    """Metadata for an IEC 61850 SCL configuration artifact."""

    document_type: str
    uri: str
    revision: str | None = None
    sha256: str | None = None
    schema_version: str | None = None
    tool_name: str | None = None
    approved: bool = False
    ieds: list[IED] = Field(default_factory=list)

    @classmethod
    def example(cls) -> "SCLConfiguration":
        return cls(
            name="station-scd-001",
            document_type="SCD",
            uri="urn:example:station:001:scd",
            revision="A",
            schema_version="2007B",
            ieds=[IED.example()],
        )


class SemanticSignal(Component):
    """Protocol-independent meaning for a status, measurement, or command."""

    signal_type: str
    source_object: Component
    unit: str | None = None
    engineering_description: str | None = None
    command_authority: str | None = None

    @classmethod
    def example(cls) -> "SemanticSignal":
        return cls(
            name="feeder-breaker-position",
            signal_type="status",
            source_object=PrimaryEquipmentComponent(name="feeder-breaker-001"),
            engineering_description="Current breaker position",
        )


class ProtocolMapping(Component):
    """Mapping from a semantic signal to a protocol-local address."""

    signal: SemanticSignal
    endpoint: ProtocolEndpoint
    protocol: ProtocolType
    point_type: str
    point_address: str
    variation: str | None = None
    class_behavior: str | None = None
    quality_supported: bool = True

    @classmethod
    def example(cls) -> "ProtocolMapping":
        return cls(
            name="feeder-breaker-dnp3-position",
            signal=SemanticSignal.example(),
            endpoint=ProtocolEndpoint.example(),
            protocol=ProtocolType.DNP3,
            point_type="binary_input",
            point_address="0",
        )
