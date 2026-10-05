import pytest
from pydantic import ValidationError

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


def test_substation_system_example_serializes(tmp_path):
    system = SubstationSystem.example()
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
