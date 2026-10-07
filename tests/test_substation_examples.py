import pytest
from pydantic import ValidationError

from gdm.systems.distribution.enums import ConnectionType
from gdm.systems.distribution.equipment import (
    CircuitBreakerEquipment,
    PowerTransformerEquipment,
)

from gdm.systems.substation import (
    AssetReference,
    Bay,
    BusbarSection,
    CircuitBreaker,
    CollectorFeeder,
    ConfigurationBaseline,
    DocumentReference,
    Disconnector,
    EarthingSwitch,
    EnergyStorageInterface,
    ExternalCircuit,
    FeederBoundary,
    IED,
    InstrumentTransformer,
    InstrumentTransformerCore,
    InterconnectionProfile,
    InverterUnit,
    LifecycleRecord,
    LineTrap,
    LogicalNode,
    MeterTest,
    MeteringPoint,
    ModelReference,
    PlantPowerController,
    PowerQualityMonitor,
    PowerTransformer,
    ProtectionFunction,
    ProtectionIED,
    ProtectionScheme,
    ProtectionSetting,
    ProtectionSettingGroup,
    ProtectionTest,
    ProtocolEndpoint,
    ProtocolMapping,
    Rating,
    RenewablePlantInterface,
    SCLConfiguration,
    SemanticSignal,
    SolarPlant,
    StandardProfile,
    StateObservation,
    StorageUnit,
    Substation,
    SubstationSystem,
    SubstationType,
    SurgeArrester,
    VoltageLevel,
    PVBlock,
    WindPlant,
    WindTurbine,
)


SUBSTATION_MODELS = [
    AssetReference,
    Bay,
    BusbarSection,
    ExternalCircuit,
    CircuitBreaker,
    CollectorFeeder,
    ConfigurationBaseline,
    DocumentReference,
    Disconnector,
    EarthingSwitch,
    EnergyStorageInterface,
    FeederBoundary,
    IED,
    InstrumentTransformer,
    InstrumentTransformerCore,
    InterconnectionProfile,
    InverterUnit,
    LifecycleRecord,
    LineTrap,
    LogicalNode,
    MeterTest,
    MeteringPoint,
    ModelReference,
    PlantPowerController,
    PowerQualityMonitor,
    PowerTransformer,
    ProtectionFunction,
    ProtectionIED,
    ProtectionScheme,
    ProtectionSetting,
    ProtectionSettingGroup,
    ProtectionTest,
    ProtocolEndpoint,
    ProtocolMapping,
    Rating,
    RenewablePlantInterface,
    SCLConfiguration,
    SemanticSignal,
    SolarPlant,
    StandardProfile,
    StateObservation,
    StorageUnit,
    Substation,
    SurgeArrester,
    VoltageLevel,
    PVBlock,
    WindPlant,
    WindTurbine,
]


@pytest.mark.parametrize("model_type", SUBSTATION_MODELS)
def test_substation_examples(model_type):
    assert isinstance(model_type.example(), model_type)


def test_substation_system_serializes(tmp_path):
    system = SubstationSystem(name="substation-system")
    system.add_component(
        Substation(name="substation", substation_type=SubstationType.DISTRIBUTION)
    )
    filename = tmp_path / "substation.json"

    system.to_json(filename, overwrite=True)
    restored = SubstationSystem.from_json(filename)

    assert restored.name == system.name
    assert len(list(restored.iter_all_components())) == len(list(system.iter_all_components()))


def test_circuit_breaker_requires_two_buses():
    bus = BusbarSection.example()

    with pytest.raises(ValidationError):
        CircuitBreaker(
            name="invalid-breaker",
            buses=[bus],
            equipment=CircuitBreakerEquipment.example(),
        )


def test_power_transformer_requires_one_bus_per_winding():
    equipment = PowerTransformerEquipment.example().model_copy(
        update={"windings": [PowerTransformerEquipment.example().windings[0]]}
    )

    with pytest.raises(ValidationError):
        PowerTransformer(
            name="invalid-transformer",
            buses=[BusbarSection.example()],
            equipment=equipment,
        )


def test_power_transformer_example_vector_group_matches_winding_connections():
    equipment = PowerTransformerEquipment.example()

    assert equipment.vector_group == "Dyn1"
    assert [winding.connection_type for winding in equipment.windings] == [
        ConnectionType.DELTA,
        ConnectionType.STAR,
    ]


def test_power_transformer_rejects_mismatched_vector_group_connections():
    equipment_data = PowerTransformerEquipment.example().model_dump()
    equipment_data["vector_group"] = "Yd1"

    with pytest.raises(ValidationError, match="winding 1"):
        PowerTransformerEquipment.model_validate(equipment_data)


def test_power_transformer_rejects_vector_group_winding_count_mismatch():
    equipment_data = PowerTransformerEquipment.example().model_dump()
    equipment_data["vector_group"] = "Dyn1d11"

    with pytest.raises(ValidationError, match="specifies 3 windings"):
        PowerTransformerEquipment.model_validate(equipment_data)
