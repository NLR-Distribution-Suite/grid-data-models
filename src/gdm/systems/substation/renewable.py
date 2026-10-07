"""Renewable, storage, collector, and interconnection profiles.

Plant-level identifiers (``plant_id``, ``point_of_interconnection_id``) refer to
objects outside the station system and remain strings. Station-owned objects
such as bays and buses use real component references.
"""

from __future__ import annotations

from infrasys import Component
from pydantic import Field

from gdm.quantities import ApparentPower, Voltage
from gdm.systems.distribution.enums import VoltageTypes
from gdm.systems.substation.enums import SubstationType
from gdm.systems.substation.topology import Bay, BusbarSection


class InterconnectionProfile(Component):
    """Utility-facing performance profile at an interconnection point."""

    profile_standard: str
    profile_edition: str
    point_of_interconnection_id: str
    nominal_voltage: Voltage
    voltage_type: VoltageTypes
    active_power_control: list[str] = Field(default_factory=list)
    reactive_power_control: list[str] = Field(default_factory=list)
    ride_through_profile_id: str | None = None
    power_quality_profile_id: str | None = None
    model_package_reference_id: str | None = None

    @classmethod
    def example(cls) -> "InterconnectionProfile":
        return cls(
            name="ibr-interconnection-profile",
            profile_standard="IEEE 2800",
            profile_edition="2022",
            point_of_interconnection_id="point-of-interconnection-001",
            nominal_voltage=Voltage(34.5, "kilovolt"),
            voltage_type=VoltageTypes.LINE_TO_LINE,
            active_power_control=["ramp_rate", "frequency_response"],
            reactive_power_control=["voltage_control", "power_factor_control"],
        )


class PlantPowerController(Component):
    """Plant-level controller for wind, solar, or hybrid IBR assets."""

    plant_id: str
    point_of_interconnection_id: str
    control_modes: list[str] = Field(default_factory=list)
    inverter_ids: list[str] = Field(default_factory=list)
    collector_feeder_ids: list[str] = Field(default_factory=list)
    interconnection_profile_id: str | None = None

    @classmethod
    def example(cls) -> "PlantPowerController":
        return cls(
            name="plant-power-controller-001",
            plant_id="solar-plant-001",
            point_of_interconnection_id="point-of-interconnection-001",
            control_modes=["voltage_control", "reactive_power_control"],
        )


class CollectorFeeder(Component):
    """MV collector feeder connecting a renewable plant block to the station."""

    plant_id: str
    station_bay: Bay | None = None
    bus: BusbarSection | None = None
    collector_voltage: Voltage
    collector_voltage_type: VoltageTypes
    generation_block_ids: list[str] = Field(default_factory=list)

    @classmethod
    def example(cls) -> "CollectorFeeder":
        return cls(
            name="solar-collector-feeder-001",
            plant_id="solar-plant-001",
            station_bay=Bay.example(),
            collector_voltage=Voltage(34.5, "kilovolt"),
            collector_voltage_type=VoltageTypes.LINE_TO_LINE,
        )


class InverterUnit(Component):
    """Power-electronic conversion unit associated with a plant block."""

    plant_id: str
    rated_apparent_power: ApparentPower
    ac_voltage: Voltage
    voltage_type: VoltageTypes
    controller_id: str | None = None
    interconnection_profile_id: str | None = None

    @classmethod
    def example(cls) -> "InverterUnit":
        return cls(
            name="pv-inverter-001",
            plant_id="solar-plant-001",
            rated_apparent_power=ApparentPower(2.5, "megavolt_ampere"),
            ac_voltage=Voltage(0.69, "kilovolt"),
            voltage_type=VoltageTypes.LINE_TO_LINE,
        )


class PVBlock(Component):
    """Aggregated PV array and inverter block."""

    plant_id: str
    dc_capacity: float = Field(..., gt=0)
    dc_capacity_unit: str = "megawatt"
    inverter_ids: list[str] = Field(default_factory=list)
    collector_feeder_id: str | None = None

    @classmethod
    def example(cls) -> "PVBlock":
        return cls(
            name="pv-block-001",
            plant_id="solar-plant-001",
            dc_capacity=3,
            inverter_ids=["pv-inverter-001"],
            collector_feeder_id="solar-collector-feeder-001",
        )


class WindTurbine(Component):
    """Wind turbine interface used by a collector plant model."""

    plant_id: str
    rated_active_power: float = Field(..., gt=0)
    rated_power_unit: str = "megawatt"
    inverter_id: str | None = None
    collector_feeder_id: str | None = None
    controller_id: str | None = None

    @classmethod
    def example(cls) -> "WindTurbine":
        return cls(
            name="wind-turbine-001",
            plant_id="wind-plant-001",
            rated_active_power=4.2,
            inverter_id="wind-inverter-001",
            collector_feeder_id="wind-collector-feeder-001",
        )


class WindPlant(Component):
    """Aggregated wind plant interface to a collector substation."""

    plant_id: str
    turbine_ids: list[str] = Field(default_factory=list)
    collector_feeder_ids: list[str] = Field(default_factory=list)
    plant_controller_id: str | None = None

    @classmethod
    def example(cls) -> "WindPlant":
        return cls(
            name="wind-plant-001",
            plant_id="wind-plant-001",
            turbine_ids=["wind-turbine-001"],
            collector_feeder_ids=["wind-collector-feeder-001"],
        )


class SolarPlant(Component):
    """Aggregated solar plant interface to a collector substation."""

    plant_id: str
    pv_block_ids: list[str] = Field(default_factory=list)
    collector_feeder_ids: list[str] = Field(default_factory=list)
    plant_controller_id: str | None = None

    @classmethod
    def example(cls) -> "SolarPlant":
        return cls(
            name="solar-plant-001",
            plant_id="solar-plant-001",
            pv_block_ids=["pv-block-001"],
            collector_feeder_ids=["solar-collector-feeder-001"],
        )


class RenewablePlantInterface(Component):
    """Substation-facing reference to a renewable or storage plant."""

    plant_id: str
    plant_type: SubstationType
    rated_apparent_power: ApparentPower
    point_of_interconnection_id: str
    collector_feeder_ids: list[str] = Field(default_factory=list)
    plant_controller_id: str | None = None
    interconnection_profile_id: str | None = None
    energy_storage_ids: list[str] = Field(default_factory=list)

    @classmethod
    def example(cls) -> "RenewablePlantInterface":
        return cls(
            name="solar-plant-interface-001",
            plant_id="solar-plant-001",
            plant_type=SubstationType.SOLAR_COLLECTOR,
            rated_apparent_power=ApparentPower(50, "megavolt_ampere"),
            point_of_interconnection_id="point-of-interconnection-001",
            plant_controller_id="plant-power-controller-001",
            interconnection_profile_id="ibr-interconnection-profile",
        )


class EnergyStorageInterface(Component):
    """Substation-facing interface for a colocated energy-storage plant."""

    plant_id: str
    point_of_interconnection_id: str
    rated_apparent_power: ApparentPower
    energy_capacity: float = Field(..., gt=0)
    energy_capacity_unit: str = "megawatt_hour"
    inverter_ids: list[str] = Field(default_factory=list)
    fire_safety_profile_id: str | None = None

    @classmethod
    def example(cls) -> "EnergyStorageInterface":
        return cls(
            name="battery-interface-001",
            plant_id="battery-plant-001",
            point_of_interconnection_id="point-of-interconnection-001",
            rated_apparent_power=ApparentPower(20, "megavolt_ampere"),
            energy_capacity=40,
        )


class StorageUnit(Component):
    """Battery or other storage unit behind a plant interface."""

    plant_id: str
    rated_apparent_power: ApparentPower
    energy_capacity: float = Field(..., gt=0)
    energy_capacity_unit: str = "megawatt_hour"
    inverter_id: str | None = None
    controller_id: str | None = None

    @classmethod
    def example(cls) -> "StorageUnit":
        return cls(
            name="storage-unit-001",
            plant_id="battery-plant-001",
            rated_apparent_power=ApparentPower(5, "megavolt_ampere"),
            energy_capacity=10,
            inverter_id="battery-inverter-001",
        )
