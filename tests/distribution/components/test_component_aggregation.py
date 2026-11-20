from io import StringIO

import pytest
from loguru import logger

from gdm.systems.distribution.components import (
    DistributionBattery,
    DistributionCapacitor,
    DistributionGenerator,
    DistributionLoad,
    DistributionSolar,
)
from gdm.systems.distribution.components.distribution_generator import GeneratorOperatingMode
from gdm.systems.distribution.enums import Phase


@pytest.mark.parametrize(
    "component_type",
    [DistributionLoad, DistributionSolar, DistributionBattery, DistributionCapacitor],
)
def test_aggregation_excludes_and_logs_out_of_service_components(component_type):
    active = component_type.example()
    if component_type is DistributionSolar:
        active.equipment.resistance = 1.0
        active.equipment.reactance = 1.0
    inactive = active.model_copy(deep=True, update={"name": "inactive", "in_service": False})
    stream = StringIO()
    sink = logger.add(stream, format="{message}")
    try:
        expected = component_type.aggregate([active], active.bus, "expected", {})
        result = component_type.aggregate([active, inactive], active.bus, "result", {})
        with pytest.raises(ValueError, match="in-service"):
            component_type.aggregate([inactive], active.bus, "empty", {})
    finally:
        logger.remove(sink)

    assert "inactive" in stream.getvalue()
    assert result.in_service
    if component_type is DistributionLoad:
        assert [p.real_power for p in result.equipment.phase_loads] == [
            p.real_power for p in expected.equipment.phase_loads
        ]
    elif component_type is DistributionCapacitor:
        assert [p.rated_reactive_power for p in result.equipment.phase_capacitors] == [
            p.rated_reactive_power for p in expected.equipment.phase_capacitors
        ]
        assert result.state == active.state
    else:
        assert result.active_power == expected.active_power
        assert result.equipment.rated_power == expected.equipment.rated_power


def test_capacitor_aggregation_preserves_bank_states_and_counts():
    first = DistributionCapacitor.example()
    first.state = [True]
    second = first.model_copy(deep=True, update={"name": "second", "state": [False]})
    for phase in second.equipment.phase_capacitors:
        phase.num_banks_on = 0
    result = DistributionCapacitor.aggregate([first, second], first.bus, "total", {})

    assert result.state == [True, False]
    assert [phase.num_banks for phase in result.equipment.phase_capacitors] == [2, 2, 2]
    assert [phase.num_banks_on for phase in result.equipment.phase_capacitors] == [1, 1, 1]


def test_generator_aggregation_sums_ratings_setpoints_and_limits_excluding_outages():
    first = DistributionGenerator.example()
    second = first.model_copy(deep=True, update={"name": "second"})
    inactive = first.model_copy(deep=True, update={"name": "inactive", "in_service": False})
    result = DistributionGenerator.aggregate([first, second, inactive], first.bus, "total", {})

    assert result.active_power == first.active_power + second.active_power
    assert result.reactive_power == first.reactive_power + second.reactive_power
    assert result.min_reactive_power == first.min_reactive_power + second.min_reactive_power
    assert result.max_reactive_power == first.max_reactive_power + second.max_reactive_power
    assert result.equipment.rated_apparent_power == (
        first.equipment.rated_apparent_power + second.equipment.rated_apparent_power
    )
    assert result.equipment.uuid != first.equipment.uuid
    assert result.equipment.synchronous_reactance_pu == first.equipment.synchronous_reactance_pu
    assert first.equipment.rated_apparent_power != result.equipment.rated_apparent_power
    with pytest.raises(ValueError, match="in-service"):
        DistributionGenerator.aggregate([inactive], first.bus, "empty", {})


@pytest.mark.parametrize("difference", ["mode", "reactance", "phase", "voltage_control"])
def test_generator_aggregation_rejects_incompatible_settings(difference):
    first = DistributionGenerator.example()
    second = first.model_copy(deep=True, update={"name": "second"})
    if difference == "mode":
        second.operating_mode = GeneratorOperatingMode.CONSTANT_PV
    elif difference == "reactance":
        second.equipment.transient_reactance_pu *= 2
    elif difference == "phase":
        second.phases = [Phase.A]
    else:
        second.voltage_setpoint_pu = 1.05
    with pytest.raises(ValueError, match="incompatible"):
        DistributionGenerator.aggregate([first, second], first.bus, "total", {})


def test_generator_aggregation_maps_split_phase_to_parent():
    first = DistributionGenerator.example().model_copy(update={"phases": [Phase.S1, Phase.S2]})
    result = DistributionGenerator.aggregate([first], first.bus, "total", {first.name: {Phase.A}})
    assert result.phases == [Phase.A]
