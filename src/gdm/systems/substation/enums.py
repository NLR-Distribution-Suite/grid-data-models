"""Enumerations used by substation design and operations models."""

from enum import Enum


class SubstationType(str, Enum):
    DISTRIBUTION = "distribution"
    WIND_COLLECTOR = "wind_collector"
    SOLAR_COLLECTOR = "solar_collector"
    HYBRID_RENEWABLE = "hybrid_renewable"


class LifecycleStatus(str, Enum):
    SPECIFIED = "specified"
    DESIGNED = "designed"
    PROCURED = "procured"
    INSTALLED = "installed"
    COMMISSIONED = "commissioned"
    IN_SERVICE = "in_service"
    OUT_OF_SERVICE = "out_of_service"
    RETIRED = "retired"


class EquipmentState(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    GROUNDED = "grounded"
    RACKED_IN = "racked_in"
    RACKED_OUT = "racked_out"
    UNKNOWN = "unknown"


class CircuitDirection(str, Enum):
    """Direction of an external circuit at the station boundary."""

    INCOMING = "incoming"
    OUTGOING = "outgoing"


class OperatingMode(str, Enum):
    NORMAL = "normal"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"
    TEST = "test"
    PLANNING = "planning"


class AssetRole(str, Enum):
    PRIMARY_EQUIPMENT = "primary_equipment"
    PROTECTION = "protection"
    CONTROL = "control"
    METERING = "metering"
    COMMUNICATIONS = "communications"
    SAFETY = "safety"


class TerminalRole(str, Enum):
    BUS_SIDE = "bus_side"
    FEEDER_SIDE = "feeder_side"
    HIGH_VOLTAGE = "high_voltage"
    LOW_VOLTAGE = "low_voltage"
    PRIMARY = "primary"
    SECONDARY = "secondary"
    NEUTRAL = "neutral"
    OTHER = "other"


class ProtectionFunctionType(str, Enum):
    OVERCURRENT = "overcurrent"
    DIRECTIONAL_OVERCURRENT = "directional_overcurrent"
    DIFFERENTIAL = "differential"
    DISTANCE = "distance"
    UNDERVOLTAGE = "undervoltage"
    OVERVOLTAGE = "overvoltage"
    UNDERFREQUENCY = "underfrequency"
    OVERFREQUENCY = "overfrequency"
    SYNCHRONISM_CHECK = "synchronism_check"
    RECLOSING = "reclosing"
    BREAKER_FAILURE = "breaker_failure"
    LOCKOUT = "lockout"
    GROUND_FAULT = "ground_fault"
    ANTI_ISLANDING = "anti_islanding"
    OTHER = "other"


class MeasurementPurpose(str, Enum):
    REVENUE = "revenue"
    CHECK = "check"
    OPERATIONAL = "operational"
    POWER_QUALITY = "power_quality"


class ProtocolType(str, Enum):
    IEC_61850 = "iec_61850"
    DNP3 = "dnp3"
    IEC_60870_5_101 = "iec_60870_5_101"
    IEC_60870_5_103 = "iec_60870_5_103"
    IEC_60870_5_104 = "iec_60870_5_104"
    OTHER = "other"


class DocumentType(str, Enum):
    SCL = "scl"
    RELAY_SETTINGS = "relay_settings"
    ONE_LINE = "one_line"
    WIRING_DIAGRAM = "wiring_diagram"
    STUDY = "study"
    TEST_REPORT = "test_report"
    OTHER = "other"
